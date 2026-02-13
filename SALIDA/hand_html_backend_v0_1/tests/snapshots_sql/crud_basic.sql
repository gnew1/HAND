-- HAND SQL v0.1 (generated)
-- module: demo

-- DML
INSERT INTO users (id, email, is_admin) VALUES (1, 'a@b.com', FALSE);
SELECT id, email FROM users WHERE id = :id;
UPDATE users SET email = :email WHERE id = :id;
DELETE FROM users WHERE id = :id;
