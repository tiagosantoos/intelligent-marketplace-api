-- Execute como proprietário das tabelas após aplicar as migrações.
-- Crie a senha depois pelo reset da role no console; não grave senha neste arquivo.
-- Uma role já existente causa erro, evitando reutilizar silenciosamente uma role administrativa.
CREATE ROLE marketplace_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA historical TO marketplace_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA historical TO marketplace_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA historical GRANT SELECT ON TABLES TO marketplace_runtime;
ALTER ROLE marketplace_runtime SET default_transaction_read_only = on;
