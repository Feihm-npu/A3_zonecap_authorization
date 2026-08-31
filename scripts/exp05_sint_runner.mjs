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

function scope(token) {
  return {
    resource: token.resource,
    actions: [...token.actions],
    maxVelocityMps: token.constraints.maxVelocityMps,
    expiresAt: token.expiresAt,
    delegationDepth: token.delegationChain.depth,
    attenuated: token.delegationChain.attenuated,
  };
}

const repo = path.resolve(argument("--sint-repo"));
const output = path.resolve(argument("--output"));
const commit = execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], {
  encoding: "utf8",
}).trim();
const modulePath = path.join(
  repo,
  "packages/capability-tokens/dist/index.js",
);
const {
  generateKeypair,
  issueCapabilityToken,
  delegateCapabilityToken,
} = await import(pathToFileURL(modulePath).href);

const authority = generateKeypair();
const parentSubject = generateKeypair();
const childSubject = generateKeypair();
const parentResult = issueCapabilityToken(
  {
    issuer: authority.publicKey,
    subject: parentSubject.publicKey,
    resource: "modbus://cell/valve",
    actions: ["set", "read"],
    constraints: { maxVelocityMps: 1.0 },
    delegationChain: { parentTokenId: null, depth: 0, attenuated: false },
    expiresAt: "2099-12-31T00:00:00.000000Z",
    revocable: true,
  },
  authority.privateKey,
);
if (!parentResult.ok) throw new Error(`parent issuance failed: ${parentResult.error}`);

const childResult = delegateCapabilityToken(
  parentResult.value,
  {
    newSubject: childSubject.publicKey,
    restrictActions: ["set"],
    tightenConstraints: { maxVelocityMps: 0.4 },
    expiresAt: "2098-12-31T00:00:00.000000Z",
  },
  parentSubject.privateKey,
);
if (!childResult.ok) throw new Error(`child delegation failed: ${childResult.error}`);

const wideningResult = delegateCapabilityToken(
  parentResult.value,
  {
    newSubject: childSubject.publicKey,
    restrictActions: ["set", "admin"],
    tightenConstraints: { maxVelocityMps: 1.5 },
    expiresAt: "2100-12-31T00:00:00.000000Z",
  },
  parentSubject.privateKey,
);
if (!wideningResult.ok) throw new Error(`widening normalization failed: ${wideningResult.error}`);

const emptyActionResult = delegateCapabilityToken(
  parentResult.value,
  {
    newSubject: childSubject.publicKey,
    restrictActions: ["admin"],
  },
  parentSubject.privateKey,
);

const sourceFiles = [
  "WHITEPAPER.md",
  "packages/capability-tokens/src/delegator.ts",
  "packages/capability-tokens/src/validator.ts",
];
const record = {
  repository: "https://github.com/sint-ai/sint-protocol.git",
  commit,
  parent: scope(parentResult.value),
  child: scope(childResult.value),
  widening_request_normalized_to: scope(wideningResult.value),
  unauthorized_only_action_request_ok: emptyActionResult.ok,
  unauthorized_only_action_error: emptyActionResult.ok
    ? null
    : emptyActionResult.error,
  source_hashes: Object.fromEntries(
    sourceFiles.map((relative) => [relative, sha256(path.join(repo, relative))]),
  ),
};
writeFileSync(output, `${JSON.stringify(record, null, 2)}\n`, "utf8");
console.log(
  JSON.stringify({
    commit,
    parent: record.parent,
    child: record.child,
    widening_request_normalized_to: record.widening_request_normalized_to,
    unauthorized_only_action_request_ok: record.unauthorized_only_action_request_ok,
  }),
);
