-- Remove one period of a table (the first half of a replacement, D-049).
DELETE FROM {table} WHERE period = %(period)s;
