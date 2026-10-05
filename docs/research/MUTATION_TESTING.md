# Controlled mutation foundation

`MutationOperator` protocol: operator ID/version, supported languages, apply and verify. Registry
supports ARCH001–005 version `1.0` on Java and TypeScript. Shared dependency insertion implements
five distinct declared architecture scenarios; JS/TSX and arbitrary application rewriting are deferred.

| Rule | Clean control | Intended change |
| --- | --- | --- |
| ARCH001 | Domain has no infrastructure dependency | Domain → Infrastructure |
| ARCH002 | Controller → Service → Repository | Extra Controller → Repository |
| ARCH003 | A → B → C | C → A closes the declared three-component SCC |
| ARCH004 | No reversed domain/application dependency | Domain → Application |
| ARCH005 | Orders isolated from Payments internals | Orders → PaymentInternal |

Operators accept deliberately marked source templates, not arbitrary AST rewrites. They return a new
file map, preserving originals. Mutation identity is UUIDv5 of namespace, base ID/content fingerprint,
operator/version and full seed/config. Manifests include changed relative files, actual before/after
byte SHA-256, base/result source fingerprints, independent expected truth, verification and diagnostics.
Same input/config gives identical source bytes and manifest. LF/UTF-8 and POSIX paths are required.

Expected POSITIVE truth is created **before** parsing the mutant. Verification uses strict intake,
Tree-sitter parsing and IAM: complete/valid model, exact locators and an actual resolved dependency.
Cycle verification checks each edge in A → B → C → A and the expected SCC member set. No detector
Finding is used as the truth oracle. Checked-in manifests replay against the base and verify each
changed-file hash. Clean NEGATIVE and mutated POSITIVE remain in the same family/split, including
language translations.

```bash
# Config is the `config` object from the matching checked-in mutation manifest.
uv run archguard benchmark mutate benchmarks/v1/dataset.json \
  --base static-java-2-clean --operator ARCH002 --config mutation-config.json \
  --output /tmp/new-mutant
```

Output must be a new directory outside the base. Verification happens in a temporary workspace
before writing output; source files appear under `repository/`, manifest as `mutation.json`.
No original fixture is modified, and no generated application executes. Typed mutation limits default
to 100 source files/1 MiB, one changed file and 1 MiB output; budgets can be lowered. Source and
manifest loaders reject symlink traversal and noncanonical paths. Adding a new scenario requires
independent expected truth, negative control and structural verification, not detector-driven labels.
