from db import fetch_one, fetch_all, execute
from db import hash_password, hash_password_legacy
from datetime import datetime


class AuthService:

    # ================= LOGIN =================
    def login(self, username, password):
        user = fetch_one("""
            SELECT id, username, role, store_id, password, password_salt
            FROM users
            WHERE username = %s
        """, (username,))

        if not user:
            return None

        valid = False

        # ===== CHECK PASSWORD =====
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

                execute("""
                    UPDATE users
                    SET password = %s, password_salt = %s
                    WHERE id = %s
                """, (new_hash, new_salt, user["id"]))

        if not valid:
            return None

        # OPTIONAL: update last_login
        execute("""
            UPDATE users
            SET last_login = %s
            WHERE id = %s
        """, (datetime.utcnow(), user["id"]))

        return {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "store_id": user["store_id"],
        }

    # ================= REGISTER =================
    def register(self, username, password, role="kasir", store_id=1):
        username = (username or "").strip()

        if not username or not password:
            raise ValueError("Username & password wajib diisi")

        h, salt = hash_password(password)

        try:
            execute("""
                INSERT INTO users (username, password, password_salt, role, store_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, h, salt, role, store_id, datetime.utcnow()))

        except Exception:
            raise ValueError("Username sudah dipakai")

    # ================= LIST USERS =================
    def list_users(self, store_id):
        rows = fetch_all("""
            SELECT id, username, role
            FROM users
            WHERE store_id = %s
            ORDER BY username
        """, (store_id,))

        return rows  # sudah dict dari RealDictCursor

    # ================= DELETE USER =================
    def delete_user(self, user_id, store_id):
        execute("""
            DELETE FROM users
            WHERE id = %s AND store_id = %s
        """, (user_id, store_id))

    # ================= CHANGE PASSWORD =================
    def change_password(self, user_id, old_password, new_password):
        user = fetch_one("""
            SELECT password, password_salt
            FROM users
            WHERE id = %s
        """, (user_id,))

        if not user:
            raise ValueError("User tidak ditemukan")

        # ===== VALIDASI PASSWORD LAMA =====
        if user["password_salt"]:
            h, _ = hash_password(old_password, user["password_salt"])
            if h != user["password"]:
                raise ValueError("Password lama salah")
        else:
            if hash_password_legacy(old_password) != user["password"]:
                raise ValueError("Password lama salah")

        # ===== UPDATE PASSWORD BARU =====
        new_hash, new_salt = hash_password(new_password)

        execute("""
            UPDATE users
            SET password = %s, password_salt = %s
            WHERE id = %s
        """, (new_hash, new_salt, user_id))