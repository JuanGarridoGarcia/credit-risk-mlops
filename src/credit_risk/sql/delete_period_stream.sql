-- Remove one period of one stream from an ops table (warnings, column profile).
DELETE FROM {table} WHERE period = %(period)s AND stream = %(stream)s;
