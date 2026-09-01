import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || index + 1 >= process.argv.length) {
    throw new Error(`missing ${name}`);
  }
  return process.argv[index + 1];
}

function sha256(filename) {
  return createHash("sha256").update(readFileSync(filename)).digest("hex");
}

function futureISO(hoursFromNow) {
  const date = new Date(Date.now() + hoursFromNow * 3_600_000);
  return date.toISOString().replace(/\.(\d{3})Z$/, ".$1000Z");
}

function request(requestId, token, resource, action) {
  return {
    requestId,
    timestamp: new Date().toISOString().replace(/\.(\d{3})Z$/, ".$1000Z"),
    agentId: token.subject,
    tokenId: token.tokenId,
    resource,
    action,
    params: {},
  };
}

function issue(issueCapabilityToken, issuer, subject, resource, action) {
  const result = issueCapabilityToken(
    {
      issuer: issuer.publicKey,
      subject: subject.publicKey,
      resource,
      actions: [action],
      constraints: { maxForceNewtons: 50, maxVelocityMps: 0.5 },
      delegationChain: { parentTokenId: null, depth: 0, attenuated: false },
      expiresAt: futureISO(12),
      revocable: true,
    },
    issuer.privateKey,
  );
  if (!result.ok) throw new Error(`token issuance failed: ${result.error}`);
  return result.value;
}

const repo = path.resolve(argument("--sint-repo"));
const output = path.resolve(argument("--output"));
const commit = execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], {
  encoding: "utf8",
}).trim();
const tokenModule = await import(
  pathToFileURL(path.join(repo, "packages/capability-tokens/dist/index.js")).href
);
const gatewayModule = await import(
  pathToFileURL(path.join(repo, "packages/policy-gateway/dist/index.js")).href
);
const {
  generateKeypair,
  issueCapabilityToken,
  RevocationStore,
} = tokenModule;
const { ApprovalQueue, PolicyGateway } = gatewayModule;

const issuer = generateKeypair();
const observer = generateKeypair();
const operatorA = generateKeypair();
const operatorB = generateKeypair();
const tokenStore = new Map();
const localRevocations = new RevocationStore();
const gateway = new PolicyGateway({
  resolveToken: (tokenId) => tokenStore.get(tokenId),
  revocationStore: localRevocations,
});

const observeToken = issue(
  issueCapabilityToken,
  issuer,
  observer,
  "ros2:///camera/front",
  "subscribe",
);
tokenStore.set(observeToken.tokenId, observeToken);
const observeRequest = request(
  "01905f7c-4e8a-7b3d-9a1e-f2c3d4e5f6a1",
  observeToken,
  "ros2:///camera/front",
  "subscribe",
);
const beforeRevocation = await gateway.intercept(observeRequest);

// Issuance is an external fact until propagation updates this resolver's store.
const issuedButNotDelivered = await gateway.intercept(observeRequest);
localRevocations.revoke(observeToken.tokenId, "exp20", "authority");
const afterDelivery = await gateway.intercept(observeRequest);

const tokenA = issue(
  issueCapabilityToken,
  issuer,
  operatorA,
  "ros2:///cmd_vel",
  "publish",
);
const tokenB = issue(
  issueCapabilityToken,
  issuer,
  operatorB,
  "ros2:///cmd_vel",
  "publish",
);
tokenStore.set(tokenA.tokenId, tokenA);
tokenStore.set(tokenB.tokenId, tokenB);
const requestA = request(
  "01905f7c-4e8a-7b3d-9a1e-f2c3d4e5f6a2",
  tokenA,
  "ros2:///cmd_vel",
  "publish",
);
const requestB = request(
  "01905f7c-4e8a-7b3d-9a1e-f2c3d4e5f6a3",
  tokenB,
  "ros2:///cmd_vel",
  "publish",
);
const escalationA = await gateway.intercept(requestA);
const escalationB = await gateway.intercept(requestB);
const quorum = { required: 2, authorized: ["alice", "bob", "carol"] };
const queue = new ApprovalQueue({ defaultTimeoutMs: 5_000 });
queue.enqueue(requestA, escalationA, quorum);
queue.enqueue(requestB, escalationB, quorum);
const firstA = queue.resolve(requestA.requestId, {
  status: "approved",
  by: "alice",
});
const duplicateA = queue.resolve(requestA.requestId, {
  status: "approved",
  by: "alice",
});
const firstB = queue.resolve(requestB.requestId, {
  status: "approved",
  by: "alice",
});
const approvalCountAfterDuplicate = queue.getApprovalCount(requestA.requestId);
localRevocations.revoke(tokenA.tokenId, "during quorum", "authority");
const secondA = queue.resolve(requestA.requestId, {
  status: "approved",
  by: "bob",
});
const secondB = queue.resolve(requestB.requestId, {
  status: "approved",
  by: "bob",
});
const revokedGatewayRecheck = await gateway.intercept(requestA);
queue.dispose();

const timeoutQueue = new ApprovalQueue({ defaultTimeoutMs: 50 });
const timeoutEvents = [];
timeoutQueue.on((event) => timeoutEvents.push(event));
const timeoutRequest = {
  ...requestB,
  requestId: "01905f7c-4e8a-7b3d-9a1e-f2c3d4e5f6a4",
};
const timeoutDecision = {
  ...escalationB,
  requestId: timeoutRequest.requestId,
  escalation: {
    ...escalationB.escalation,
    timeoutMs: 50,
    fallbackAction: "deny",
  },
};
timeoutQueue.enqueue(timeoutRequest, timeoutDecision, quorum);
timeoutQueue.resolve(timeoutRequest.requestId, {
  status: "approved",
  by: "alice",
});
await new Promise((resolve) => setTimeout(resolve, 150));
const timeoutResolution = timeoutEvents.find(
  (event) => event.type === "resolved" && event.resolution.status === "timeout",
);
timeoutQueue.dispose();

const sourceFiles = [
  "WHITEPAPER.md",
  "packages/capability-tokens/src/revocation.ts",
  "packages/policy-gateway/src/gateway.ts",
  "packages/policy-gateway/src/approval-flow.ts",
  "packages/persistence/src/in-memory-revocation-bus.ts",
  "packages/persistence/src/redis-revocation-bus.ts",
];
const record = {
  repository: "https://github.com/sint-ai/sint-protocol.git",
  commit,
  sourceHashes: Object.fromEntries(
    sourceFiles.map((relative) => [relative, sha256(path.join(repo, relative))]),
  ),
  localRevocationTrace: {
    beforeRevocation: beforeRevocation.action,
    issuedButNotDelivered: issuedButNotDelivered.action,
    afterDelivery: afterDelivery.action,
    afterDeliveryPolicy: afterDelivery.denial?.policyViolated ?? null,
  },
  quorumConflictTrace: {
    gatewayInitialActions: [escalationA.action, escalationB.action],
    firstVotesPending: firstA === undefined && firstB === undefined,
    duplicateVoteResolution: duplicateA?.status ?? null,
    approvalCountAfterDuplicate,
    revokedRequestResolution: secondA?.status ?? null,
    otherRequestResolution: secondB?.status ?? null,
    approvedSameResourceRequests: [secondA, secondB].filter(
      (resolution) => resolution?.status === "approved",
    ).length,
    crossRequestWinner: null,
    revokedGatewayRecheck: revokedGatewayRecheck.action,
    revokedGatewayRecheckPolicy:
      revokedGatewayRecheck.denial?.policyViolated ?? null,
  },
  missingApprovalTrace: {
    timedOut: timeoutResolution !== undefined,
    fallbackAction: timeoutResolution?.resolution.fallbackAction ?? null,
    pendingAtEnd: timeoutQueue.size,
  },
};
writeFileSync(output, `${JSON.stringify(record, null, 2)}\n`, "utf8");
console.log(JSON.stringify(record));

