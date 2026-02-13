-- HAND SQL v0.1 (generated)
-- module: demo

-- DDL
CREATE TABLE IF NOT EXISTS users (
  id INTEGER NOT NULL,
  email TEXT NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  total REAL NOT NULL,
  PRIMARY KEY (id)
);


-- DML
