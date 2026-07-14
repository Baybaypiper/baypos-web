from database import connect, hash_password, hash_password_legacy


class AuthService:

    # ================= LOGIN =================
    def login(self, username, password):
        conn = connect()
        c = conn.cursor()

        try:
            c.execute("""
                SELECT id, username, role, store_id, password, password_salt
                FROM users WHERE username=?
            """, (username,))
            user = c.fetchone()

            if not user:
                return None

            valid = False

            # ================= CHECK PASSWORD =================
            if user["password_salt"]:
                # NEW SYSTEM (salted)
                h, _ = hash_password(password, user["password_salt"])
                valid = (h == user["password"])

            else:
                # LEGACY SYSTEM (no salt)
                if user["password"] == hash_password_legacy(password):
                    valid = True

                    # AUTO UPGRADE KE SALTED
                    new_hash, new_salt = hash_password(password)
                    c.execute("""
                        UPDATE users 
                        SET password=?, password_salt=? 
                        WHERE id=?
                    """, (new_hash, new_salt, user["id"]))
                    conn.commit()

            if not valid:
                return None

            return {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "store_id": user["store_id"],
            }

        finally:
            conn.close()

    # ================= REGISTER =================
    def register(self, username, password, role="kasir", store_id=1):
        conn = connect()
        c = conn.cursor()

        username = (username or "").strip()

        if not username or not password:
            conn.close()
            raise ValueError("Username & password wajib diisi")

        h, salt = hash_password(password)

        try:
            c.execute("""
                INSERT INTO users (username, password, password_salt, role, store_id)
                VALUES (?, ?, ?, ?, ?)
            """, (username, h, salt, role, store_id))

            conn.commit()

        except Exception:
            raise ValueError("Username sudah dipakai")

        finally:
            conn.close()

    # ================= LIST USERS =================
    def list_users(self, store_id):
        conn = connect()
        c = conn.cursor()

        try:
            c.execute("""
                SELECT id, username, role 
                FROM users 
                WHERE store_id=? 
                ORDER BY username
            """, (store_id,))

            return [dict(r) for r in c.fetchall()]

        finally:
            conn.close()

    # ================= DELETE USER =================
    def delete_user(self, user_id, store_id):
        conn = connect()
        c = conn.cursor()

        try:
            c.execute("""
                DELETE FROM users 
                WHERE id=? AND store_id=?
            """, (user_id, store_id))

            conn.commit()

        finally:
            conn.close()

    # ================= OPTIONAL: CHANGE PASSWORD =================
    def change_password(self, user_id, old_password, new_password):
        conn = connect()
        c = conn.cursor()

        try:
            c.execute("""
                SELECT password, password_salt 
                FROM users WHERE id=?
            """, (user_id,))
            user = c.fetchone()

            if not user:
                raise ValueError("User tidak ditemukan")

            # cek password lama
            if user["password_salt"]:
                h, _ = hash_password(old_password, user["password_salt"])
                if h != user["password"]:
                    raise ValueError("Password lama salah")
            else:
                if hash_password_legacy(old_password) != user["password"]:
                    raise ValueError("Password lama salah")

            # update password baru
            new_hash, new_salt = hash_password(new_password)

            c.execute("""
                UPDATE users 
                SET password=?, password_salt=? 
                WHERE id=?
            """, (new_hash, new_salt, user_id))

            conn.commit()

        finally:
            conn.close()