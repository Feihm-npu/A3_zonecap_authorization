// Exp-25 timing runner for pinned SINT on the frozen C5 common-subset corpus.
//
// The timed region is one `await gateway.intercept(request)` call of the pinned
// SINT PolicyGateway, configured as in exp-20: an in-memory token resolver and
// a local RevocationStore.  Tokens, delegations, expired twins, and request
// objects are built before warm-up.  The Python side supplies the request order
// and computes every percentile from the returned raw samples.

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { pathToFileURL } from "node:url";
import path from "node:path";

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || index + 1 >= process.argv.length) {
    throw new Error(`missing ${name}`);
  }
  return process.argv[index + 1];
}

function sha256Hex(text) {
  return createHash("sha256").update(text).digest("hex");
}

function isoAfter(milliseconds) {
  const date = new Date(Date.now() + milliseconds);
  return date.toISOString().replace(/\.(\d{3})Z$/, ".$1000Z");
}

function requestId(index) {
  const hex = index.toString(16).padStart(12, "0");
  return `01905f7c-4e8a-7b3d-9a1e-${hex}`;
}

function unwrap(result, what) {
  if (!result.ok) throw new Error(`${what} failed: ${result.error}`);
  return result.value;
}

const sintRepo = path.resolve(argument("--sint-repo"));
const corpusDir = path.resolve(argument("--corpus-dir"));
const orderPath = path.resolve(argument("--order"));
const outputDir = path.resolve(argument("--output-dir"));
const warmup = Number(argument("--warmup"));
const measured = Number(argument("--measured"));
const revokedCount = Number(argument("--revoked"));
mkdirSync(outputDir, { recursive: true });

const commit = execFileSync("git", ["-C", sintRepo, "rev-parse", "HEAD"], {
  encoding: "utf8",
}).trim();
const tokens = await import(
  pathToFileURL(path.join(sintRepo, "packages/capability-tokens/dist/index.js")).href
);
const gatewayModule = await import(
  pathToFileURL(path.join(sintRepo, "packages/policy-gateway/dist/index.js")).href
);
const {
  delegateCapabilityToken,
  generateUUIDv7,
  getPublicKey,
  issueCapabilityToken,
  RevocationStore,
} = tokens;
const { PolicyGateway } = gatewayModule;

const steps = readFileSync(path.join(corpusDir, "sint_subset", "steps.jsonl"), "utf8")
  .split("\n")
  .filter((line) => line.length > 0)
  .map((line) => JSON.parse(line));
const scopes = JSON.parse(readFileSync(path.join(corpusDir, "scopes.json"), "utf8"));
const orderBytes = readFileSync(orderPath);
const order = new Uint32Array(orderBytes.buffer, orderBytes.byteOffset, orderBytes.length / 4);
if (order.length !== warmup + measured) {
  throw new Error(`order has ${order.length} positions, expected ${warmup + measured}`);
}

const keys = new Map();
function keyFor(kind, name) {
  const id = `${kind}|${name}`;
  if (!keys.has(id)) {
    const privateKey = sha256Hex(`zonecap-c5-sint-keys-v1|${id}`);
    keys.set(id, { privateKey, publicKey: getPublicKey(privateKey) });
  }
  return keys.get(id);
}

function resource(zone, asset) {
  return `modbus://${zone}/${asset}`;
}

const tokenStore = new Map();
const normal = new Map();
const expiredTwin = new Map();
const needed = new Set(steps.map((step) => step.leaf));
const twinNeeded = new Set(
  steps.filter((step) => step.context.tick > scopes[step.leaf].ticks[1]).map((step) => step.leaf),
);
const longExpiry = isoAfter(24 * 3_600_000);
let latestTwinExpiry = 0;

function scopeChain(leaf) {
  const [architecture, grant, depthTag] = leaf.split(":");
  const depth = Number(depthTag.slice(1));
  return Array.from({ length: depth + 1 }, (_, d) => `${architecture}:${grant}:d${d}`);
}

function issueScope(scopeId, parentId, expiresAt) {
  const scope = scopes[scopeId];
  const subject = keyFor("subject", scope.subject);
  if (parentId === null) {
    const architecture = scopeId.split(":")[0];
    const authority = keyFor("issuer", `issuer:${architecture}`);
    return unwrap(
      issueCapabilityToken(
        {
          issuer: authority.publicKey,
          subject: subject.publicKey,
          resource: resource(scope.target_zone, scope.assets[0]),
          actions: [...scope.actions],
          constraints: { maxVelocityMps: scope.parameter[1] },
          delegationChain: { parentTokenId: null, depth: 0, attenuated: false },
          expiresAt,
          revocable: true,
        },
        authority.privateKey,
      ),
      `issue ${scopeId}`,
    );
  }
  const parent = normal.get(parentId);
  const delegator = keyFor("subject", scopes[parentId].subject);
  return unwrap(
    delegateCapabilityToken(
      parent,
      {
        newSubject: subject.publicKey,
        restrictActions: [...scope.actions],
        tightenConstraints: { maxVelocityMps: scope.parameter[1] },
        expiresAt,
      },
      delegator.privateKey,
    ),
    `delegate ${scopeId}`,
  );
}

const setupStarted = process.hrtime.bigint();
for (const leaf of [...needed].sort()) {
  const chain = scopeChain(leaf);
  chain.forEach((scopeId, depth) => {
    if (!normal.has(scopeId)) {
      const token = issueScope(scopeId, depth === 0 ? null : chain[depth - 1], longExpiry);
      normal.set(scopeId, token);
      tokenStore.set(token.tokenId, token);
    }
  });
  if (twinNeeded.has(leaf)) {
    // Each twin expires 1.5 s after its own issuance, so slow signing cannot
    // push an issuance past its expiry.
    const twinExpiry = isoAfter(1_500);
    latestTwinExpiry = Math.max(latestTwinExpiry, Date.parse(twinExpiry));
    const twin = issueScope(leaf, chain.length === 1 ? null : chain[chain.length - 2], twinExpiry);
    expiredTwin.set(leaf, twin);
    tokenStore.set(twin.tokenId, twin);
  }
}

const revocationStore = new RevocationStore();
for (let index = 0; index < revokedCount; index += 1) {
  revocationStore.revoke(generateUUIDv7(), "exp25 preload", "zonecap-c5");
}
const gateway = new PolicyGateway({
  resolveToken: (tokenId) => tokenStore.get(tokenId),
  revocationStore,
});

const unauthorized = keyFor("subject", "unauthorized_subject");
const timestamp = new Date().toISOString().replace(/\.(\d{3})Z$/, ".$1000Z");
const requests = steps.map((step, index) => {
  const scope = scopes[step.leaf];
  const tokenSource =
    step.context.tick > scope.ticks[1] ? expiredTwin.get(step.leaf) : normal.get(step.leaf);
  const agent =
    step.subject === scope.subject ? keyFor("subject", scope.subject) : unauthorized;
  return {
    requestId: requestId(index),
    timestamp,
    agentId: agent.publicKey,
    tokenId: tokenSource.tokenId,
    resource: resource(step.request.zd, step.request.a),
    action: step.request.o,
    params: {},
    physicalContext: { currentVelocityMps: step.request.u },
  };
});
const setupStopped = process.hrtime.bigint();

// Expired twins must be past their expiry before any decision is observed.
while (Date.now() < latestTwinExpiry + 250) {
  await new Promise((resolve) => setTimeout(resolve, 50));
}

for (let index = 0; index < warmup; index += 1) {
  await gateway.intercept(requests[order[index]]);
}

const samples = new BigUint64Array(measured);
const actions = new Array(measured);
const reasons = new Array(measured);
const loopStarted = process.hrtime.bigint();
for (let index = 0; index < measured; index += 1) {
  const request = requests[order[warmup + index]];
  const started = process.hrtime.bigint();
  const decision = await gateway.intercept(request);
  const stopped = process.hrtime.bigint();
  samples[index] = stopped - started;
  actions[index] = decision.action;
  reasons[index] = decision.denial?.policyViolated ?? null;
}
const loopStopped = process.hrtime.bigint();

const raw = Buffer.alloc(measured * 8);
for (let index = 0; index < measured; index += 1) {
  raw.writeBigUInt64LE(samples[index], index * 8);
}
writeFileSync(path.join(outputDir, "raw_samples_ns.bin.gz"), gzipSync(raw));
const lines = [];
for (let index = 0; index < measured; index += 1) {
  lines.push(JSON.stringify([index, order[warmup + index], actions[index], reasons[index]]));
}
writeFileSync(path.join(outputDir, "sint_decisions.jsonl.gz"), gzipSync(`${lines.join("\n")}\n`));
const counts = {};
for (const action of actions) counts[action] = (counts[action] ?? 0) + 1;
writeFileSync(
  path.join(outputDir, "sint_meta.json"),
  `${JSON.stringify(
    {
      sint_commit: commit,
      node: process.version,
      v8: process.versions.v8,
      steps: steps.length,
      warmup,
      measured,
      tokens_issued: tokenStore.size,
      expired_twins: expiredTwin.size,
      revoked_preloaded: revokedCount,
      setup_ns: Number(setupStopped - setupStarted),
      measured_loop_wall_ns: Number(loopStopped - loopStarted),
      decision_counts: counts,
      resource_scheme: "modbus://<target_zone>/<asset>",
      timed_call: "await PolicyGateway.intercept(request)",
    },
    null,
    2,
  )}\n`,
);
