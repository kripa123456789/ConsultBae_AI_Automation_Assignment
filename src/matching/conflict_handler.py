def log_conflict(conn, person_id, attribute_name, source_system_1, value_1, source_system_2, value_2, strategy):
    """
    Logs an entry into the entity_conflicts table when contradictory information is detected.
    Idempotent on re-runs.
    """
    conn.execute(
        """
        INSERT INTO entity_conflicts
        (person_id, attribute_name, source_system_1, source_1_value, source_system_2, source_2_value, resolution_strategy)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (person_id, attribute_name, source_system_1, source_system_2) DO NOTHING;
        """,
        (person_id, attribute_name, source_system_1, str(value_1), source_system_2, str(value_2), strategy)
    )
