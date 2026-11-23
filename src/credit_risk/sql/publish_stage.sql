-- Move the validated month from its stage table into the clean table.
INSERT INTO {table} SELECT * FROM {stage};
