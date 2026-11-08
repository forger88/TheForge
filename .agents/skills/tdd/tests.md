# Good and Bad Tests

## Good Tests

**Integration-style**: Test through real interfaces, not mocks of internal parts.

```typescript
// GOOD: Tests observable behavior
test("user can checkout with valid cart", async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe("confirmed");
});
```

Characteristics:

- Tests behavior users/callers care about
- Uses public API only
- Survives internal refactors
- Describes WHAT, not HOW
- One logical assertion per test

## Bad Tests

**Implementation-detail tests**: Coupled to internal structure.

```typescript
// BAD: Tests implementation details
test("checkout calls paymentService.process", async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

Red flags:

- Mocking internal collaborators
- Testing private methods
- Asserting on call counts/order
- Test breaks when refactoring without behavior change
- Test name describes HOW not WHAT
- Verifying through external means instead of interface

```typescript
// BAD: Bypasses interface to verify
test("createUser saves to database", async () => {
  await createUser({ name: "Alice" });
  const row = await db.query("SELECT * FROM users WHERE name = ?", ["Alice"]);
  expect(row).toBeDefined();
});

// GOOD: Verifies through interface
test("createUser makes user retrievable", async () => {
  const user = await createUser({ name: "Alice" });
  const retrieved = await getUser(user.id);
  expect(retrieved.name).toBe("Alice");
});
```

**Tautological tests**: Expected value restates the implementation, so the test passes by construction.

```typescript
// BAD: Expected value is recomputed the way the code computes it
test("calculateTotal sums line items", () => {
  const items = [{ price: 10 }, { price: 5 }];
  const expected = items.reduce((sum, i) => sum + i.price, 0);
  expect(calculateTotal(items)).toBe(expected);
});

// GOOD: Expected value is an independent, known literal
test("calculateTotal sums line items", () => {
  expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
});
```

**Golden and snapshot tests** (Default): Agents don't write them. A golden file or snapshot records whatever the code printed, so it asserts the implementation back to itself. When one goes red, the cheap fix is to regenerate it, and no human has time to review that diff, so a regenerated golden tests nothing. When the exact text really is the requirement (a user-facing message, a wire format another system parses), write it in the test as a short literal, where a reviewer sees it in the diff.

```typescript
// BAD: Whole output pinned to a captured file
test("overdue report renders", () => {
  expect(renderOverdueReport(invoices)).toMatchSnapshot();
});

// GOOD: Asserts what the report promises
test("overdue report lists each invoice once, oldest first", () => {
  const lines = renderOverdueReport(invoices).split("\n");
  const a = lines.findIndex((l) => l.includes("INV-A")); // due Monday
  const b = lines.findIndex((l) => l.includes("INV-B")); // due Tuesday
  expect(lines.filter((l) => l.includes("INV-A"))).toHaveLength(1);
  expect(a).toBeLessThan(b);
});
```

Enforced, not just advised: the `no-snapshot-assertions` pre-commit hook (`scripts/check_no_snapshots.py`) bans the common snapshot-assertion APIs and snapshot libraries; stage 0 extends its pattern list for the project's own languages (`.forge/code-shape-rules.md`, "No goldens or snapshots").

**Overspecified tests** (Default): The assertion pins more than the behaviour promises (full strings, field order, incidental formatting), so a change to wording or layout breaks many tests that should not care. Assert only the properties a caller relies on, so each test has one reason to fail. ("Overspecified Software" and "Fragile Test" in Meszaros, _xUnit Test Patterns_.)

## Further techniques

The tools named here differ by language; `docs/agents/testing-tools.md` lists which ones this repo uses.

- **Property-based tests** suit parsers, serialisers, reports and orderings: state the invariant (round-trips, every input item appears once, output is sorted) and let the library generate inputs, including the edge cases nobody writes by hand. Add the library the first time a ticket needs it.
- **Mutation testing** changes the code under test in small ways and reports which changes no test catches. It is a periodic audit of one module's tests (for gaps, and as evidence before cutting tests), not the per-guard check: "Guard-removal verification" in `SKILL.md` stays manual, because a mutation run covers a whole module and takes minutes to hours. Don't call guard-removal verification "mutation testing", even though both work by changing code and watching a test's reaction: guard-removal verification is the routine, ungated, one-guard-at-a-time check every build thread already does every ticket; mutation testing is the tool-driven, whole-module sample this gate applies to. **Never run a mutation tool without checking with the human first**, every time (Never).
