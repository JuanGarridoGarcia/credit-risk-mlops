-- Step 2.3, D-058: one clean load a version was built from.
INSERT INTO ops.training_set_loads (version, load_id) VALUES (%(version)s, %(load_id)s);
