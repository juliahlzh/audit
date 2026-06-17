# Database Schema FEWS Dana Masuk

## Tabel `users`

- `id` integer primary key
- `username` unik
- `full_name`
- `password_hash`
- `role` (`admin`, `auditor`, `viewer`)
- `created_at`

## Tabel `branch_inputs` (Input Cabang)

- `id` integer primary key
- `transaction_date`
- `branch_name`
- `customer_name`
- `amount_should_pay`
- `amount_input_branch`
- `payment_method` (`transfer` / `tunai`)
- `invoice_code`
- `notes`
- `created_at`

## Tabel `bank_mutations` (Mutasi Dana Masuk)

- `id` integer primary key
- `incoming_date`
- `sender_name`
- `amount_in`
- `company_account`
- `mutation_description`
- `notes`
- `created_at`

## Tabel `matching_results`

- `id` integer primary key
- `branch_input_id` foreign key nullable
- `bank_mutation_id` foreign key nullable
- `status` (`MATCHED` / `NEED REVIEW` / `UNMATCHED`)
- `risk_score`
- `risk_level` (`Low` / `Medium` / `High Alert`)
- `mismatch_type`
- `nominal_gap`
- `name_similarity`
- `date_gap_days`
- `confidence`
- `match_reason`
- `created_at`
- `updated_at`

## Tabel `audit_logs`

- `id` integer primary key
- `transaction_id` foreign key nullable (legacy)
- `user_id` foreign key nullable
- `action`
- `status`
- `notes`
- `created_at`
