"""Supabase client scoped to one Streamlit session. RLS is the authorization boundary."""


def new_client(url, public_key):
    from supabase import create_client, ClientOptions

    return create_client(url, public_key, options=ClientOptions(persist_session=False, auto_refresh_token=True))


def current_user(client):
    session = client.auth.get_session()
    return session.user if session else None


def read_meals(client, user_id):
    records, offset = [], 0
    while True:
        batch = client.table("food_meals").select("*").eq("user_id", user_id).order("meal_date", desc=True).order("id").range(offset, offset + 499).execute().data
        records.extend(batch)
        if len(batch) < 500:
            return records
        offset += 500


def write_meal(client, user_id, meal):
    row = dict(meal, user_id=user_id)
    # Retry after a network timeout uses the same UUID. Existing records are never overwritten.
    client.table("food_meals").upsert(row, on_conflict="id", ignore_duplicates=True).execute()


def read_profile(client, user_id):
    data = client.table("food_profiles").select("settings").eq("user_id", user_id).execute().data
    return data[0]["settings"] if data else {}


def write_profile(client, user_id, settings):
    client.table("food_profiles").upsert({"user_id": user_id, "settings": settings}, on_conflict="user_id").execute()
