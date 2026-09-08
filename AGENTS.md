# Repository instructions

## Publication boundary

Do not include or refer to privately supplied technical source material anywhere
in this repository. This applies to code, comments, documentation, tests,
filenames, reports, generated artifacts, caches and ignored local records.
Do not retain contributor identities, correspondence, source filenames or paths,
source hashes, listing excerpts, address maps, or source-specific inventories.
Ignoring a file or excluding it from a release does not satisfy this rule.

Document the implemented mathematics, numerical operation order, precision cuts
and recorded experiments directly. Preserve attribution to publicly available
sources only for the claims those sources support. Validation does not establish
independent discovery; do not describe a supplied structure as independently
recovered without a documented derivation. Records that cannot meet this boundary
must remain outside the repository.

Before finishing a change, inspect the entire changed content and any generated
artifacts for this boundary, including comments, examples, links and filenames.
Apply the same restriction to commit messages and other published descriptions.

## Editing rules

- Never use force flags for file or folder deletion or other destructive actions.
  If an ordinary operation fails, stop and report it.
- Do not delete code comments unless removing the entire code section they
  describe. Preserve their technical explanations when rewriting comments.
- Do not put the repository owner's name or email address into a code file or
  document unless explicitly requested.
- Follow [the documentation guideline](docs/code-documentation-guidelines.md)
  for numerical explanations and verification.
