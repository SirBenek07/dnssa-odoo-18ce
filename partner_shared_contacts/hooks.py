def post_init_hook(env):
    # Keep existing parent/child links visible in the new shared relation.
    env.cr.execute(
        """
        INSERT INTO res_partner_shared_contact_rel (owner_id, contact_id)
        SELECT DISTINCT parent_id, id
        FROM res_partner
        WHERE parent_id IS NOT NULL
          AND parent_id != id
          AND active = TRUE
        ON CONFLICT DO NOTHING
        """
    )
