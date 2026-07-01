# pycca grammar cannot parse attribute-access chains longer than 2 segments

**ID:** PARSE-001
**Status:** Solved
**Domain/Component:** pycca parser (pycca/grammar.py)

## Root Cause

`atom`'s only bare-attribute production was `NAME "." NAME -> dotted_name` — exactly
two segments, no recursion. `access_chain` looks like it might cover longer chains,
but its base case requires the first hop to already be a method call
(`NAME "." NAME "(" arglist? ")" -> method_call`), so a pure attribute chain
(`a.b.c`, no calls anywhere) has no valid derivation through it either. The same gap
also blocked a dotted chain that *ends* in a call, e.g. `self.steps.size()`
(3 segments before the call — `access_chain`'s base only matches exactly 2).

Result: `rcvd_evt.action.action_type`, `self.current_step_index < self.steps.size()`,
and any other 3+-segment bare attribute chain failed to parse in both
GUARD_PARSER (`start="expr"`) and STATEMENT_PARSER (`start="start"`), since both
share the same `atom`/`access_chain` rules.

Today this only surfaces as a guard-completeness warning ("Guard expression cannot
be parsed") from `_check_guard_completeness` in `tools/validation.py`, since that's
the only place GUARD_PARSER is run against model content. STATEMENT_PARSER is not
run against action-body expressions during validation at all, so the same construct
inside an action body (e.g. `self.reason = rcvd_evt.action.detail;`) parsed-failed
silently — the bug was latent there too, just unvalidated.

## Fix Applied

1. Made `dotted_name` a self-recursive rule instead of an inline 2-segment production:
   ```
   dotted_name: NAME "." NAME
              | dotted_name "." NAME
   ```
   Referenced from `atom` in place of the old `NAME "." NAME -> dotted_name`.

2. Added a second `access_chain` alternative so a dotted chain of any depth can also
   terminate in a method call (`self.steps.size()`, `rcvd_evt.a.b.method()`):
   ```
   access_chain: NAME "." NAME "(" arglist? ")"               -> method_call
               | dotted_name "." NAME "(" arglist? ")"         -> method_call
               | access_chain "." NAME "(" arglist? ")"        -> chained_method_call
               | access_chain "." NAME                         -> chained_attr_access
   ```
   The two `method_call` alternatives partition cleanly on segment count (exactly 2
   vs. 3+ before the call) — no Earley ambiguity between them, and `dotted_name`
   never contains `"("` so it can't collide with `access_chain`'s call-anchored path.

3. **Regression caught during fix, before landing:** giving `dotted_name` its own
   rule name (rather than an inline atom alias) meant `atom: ... | dotted_name`
   started wrapping the parse in an extra `Tree('atom', [Tree('dotted_name', ...)])`
   node, where previously (`NAME "." NAME -> dotted_name`) the alias replaced the
   atom node outright — no wrapper. `tools/validation.py`'s `_extract_var_names` /
   `_tree_to_z3` unwrap loops stop at the first node whose `.data` isn't
   `add_expr`/`mul_expr`, so they never saw past the new `atom` wrapper down to
   `dotted_name`, silently breaking Z3 guard-completeness analysis for *every*
   `rcvd_evt.<param>` guard (not just 3+-segment ones) — caught by manually
   re-running `_extract_var_names`/`_tree_to_z3` against a 2-segment case and
   diffing the parse tree against `git stash` (pre-fix) output.

   Fixed by marking `atom` as an inlining rule (`?atom` instead of `atom`), which
   restores the pre-fix tree shape for every single-child atom alternative
   (`dotted_name`, `access_chain`, parenthesized `expr`, `lambda_expr`,
   `select_expr`) — Lark drops the wrapper node when there's exactly one child and
   no alias, matching how the aliased alternatives (`-> number`, `-> name`, etc.)
   already behaved.

4. `compiler/transformer.py`'s `ActionTransformer.dotted_name()`/`method_call()`
   needed no change: both are applied bottom-up by Lark's `Transformer`, and their
   fallback branches (`f'{obj}["{attr}"]'`, generic `f"{obj}.{method}({args})"`)
   already treat `children[0]` as an arbitrary pre-transformed expression string, so
   nested chains compose for free — `rcvd_evt.action.action_type` ->
   `params["action"]["action_type"]`, `self.steps.size()` ->
   `len(self_dict["steps"])` (the `size` special-case in `method_call()` fires
   before the `obj == "self"` check, so it's unaffected by `obj` no longer being a
   bare `"self"` token for the deeper-chain path).

5. `tools/validation.py`'s `_extract_var_names` / `_tree_to_z3` still only
   special-case exactly 2-segment `rcvd_evt.<param>` dotted_name nodes (confirmed
   correct behavior post-`?atom`-fix via a live regression test). For a 3+-segment
   chain, `children[0]` is a nested `Tree` rather than a `rcvd_evt` token, so the
   `str(left.children[0]) == "rcvd_evt"` check fails and the guard is treated as
   not-analyzable — same "skip, don't crash" behavior as any other unrecognized
   guard shape today. No change needed for that path.

Left assignment targets (`assignment`, `var_assignment`) are still 2-segment only
(`self.attr = expr;`, `var.attr = expr;`) — out of scope for this issue, which is
about attribute chains in expression (RHS) position.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-07-01 | pycca/grammar.py | `dotted_name` made self-recursive; `access_chain` gained a `dotted_name "." NAME "(" arglist? ")"` alternative; `atom` changed to `?atom` to preserve pre-fix tree shape |
| 2026-07-01 | tests/test_pycca_grammar.py | Added guard/statement chain-depth tests, dotted-chain-then-call test, regression checks |
| 2026-07-01 | tests/test_compiler_transformer.py | Added codegen tests for nested dotted_name chains and dotted-chain-then-`.size()` |
| 2026-07-01 | tests/test_validation.py | Added regression test locking in that `rcvd_evt.<param>` guards are still analyzed by Z3 after the `?atom` change |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| tests/test_pycca_grammar.py | test_guard_dotted_chain_three_segments | Yes | Yes |
| tests/test_pycca_grammar.py | test_guard_dotted_chain_four_segments | Yes | Yes |
| tests/test_pycca_grammar.py | test_guard_dotted_chain_then_method_call | Yes | Yes |
| tests/test_pycca_grammar.py | test_statement_dotted_chain_three_segments | Yes | Yes |
| tests/test_pycca_grammar.py | test_dotted_chain_two_segments_still_parses | No (regression check) | Yes |
| tests/test_pycca_grammar.py | test_method_call_chain_still_parses | No (regression check) | Yes |
| tests/test_compiler_transformer.py | test_guard_nested_dotted_name_chain | Yes | Yes |
| tests/test_compiler_transformer.py | test_nested_dotted_name_codegen | Yes | Yes |
| tests/test_compiler_transformer.py | test_dotted_chain_then_size_call | Yes | Yes |
| tests/test_validation.py | test_guard_dotted_rcvd_evt_var_still_analyzed | No (regression check — would have failed against the intermediate `atom`-wrapping fix, before the `?atom` correction) | Yes |

Full suite (`pytest tests/`) run after the fix: 712 passed, 1 pre-existing failure
(`test_elevator_scenarios.py::test_scenario_1_door_cycle`) confirmed unrelated —
reproduced identically on `master` via `git stash` before this fix was applied.
