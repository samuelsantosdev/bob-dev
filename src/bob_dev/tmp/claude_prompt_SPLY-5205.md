## Objective
Implement asynchronous recalculation of VAT fields on temporary invoices and their related order items when a product's VAT percentage is updated via the Merch Tool product detail endpoint.

## Context
- Merch app handles product catalog updates (`merch/api/products/{id}/` PUT).
- Core models (see `core/models.py`): `Product` (vat field), `Invoice`/`InvoiceItem` (is_locked, vat, vat_p), `Order`/`OrderItem` (vat, total_vat).
- Accounting app manages invoice logic and temporary invoice handling.
- Use existing patterns from `accounting/logic.py` and `merch/` product views/serializers.
- Follow CLAUDE.md guidance for actions.py, tasks.py (Celery), and avoiding N+1 via select_related/prefetch_related on querysets.

## Implementation Steps
1. In the Merch product update flow (PUT handler), detect VAT percentage change on `Product`.
2. On change, enqueue a Celery task (new or existing in accounting/tasks.py) passing product ID and new VAT value.
3. Task implementation: query temporary invoices (`is_locked=False`) containing the product via InvoiceItem, using optimized queryset with select_related on invoice/order relationships.
4. Recalculate and persist: `InvoiceItem.vat_p`, `InvoiceItem.vat`, `Invoice.vat` for affected temporary invoices.
5. For orders linked to those invoices, recalculate and persist `OrderItem.vat` and `Order.total_vat`.
6. Ensure all updates occur inside `@transaction.atomic` blocks; trigger no additional signals or side effects beyond VAT recalculation.
7. Add task to accounting or merch tasks module following existing Celery patterns.

## Test Scenarios
- Use `accounting/tests/test_logic.py` or new `test_vat_recalculation.py` with `FakeDataTestCase` + `DataModelMixin`.
- Test case 1: Update product VAT via API → verify Celery task enqueued and temporary invoice VAT fields updated (use `freeze_time` if timestamps involved).
- Test case 2: Locked invoices (`is_locked=True`) remain unchanged.
- Test case 3: OrderItem and Order total_vat recalculated only for orders tied to updated temporary invoices.
- Test case 4: N+1 prevention verified via `assertNumQueries` on task execution with multiple invoices/items.
- Integration test: full API PUT call triggers async recalculation (mock task or use test settings).

## Acceptance Criteria
- [ ] PUT to `merch/api/products/{id}/` updating `product.vat` triggers async recalculation.
- [ ] Temporary invoices (`is_locked=False`) have `invoiceitem.vat_p`, `invoiceitem.vat`, `invoice.vat` recalculated.
- [ ] Orders in those invoices have `orderitem.vat` and `order.total_vat` recalculated.
- [ ] Locked invoices and unrelated orders unaffected.
- [ ] All operations performed asynchronously via Celery task.
- [ ] No N+1 queries introduced in recalculation logic.