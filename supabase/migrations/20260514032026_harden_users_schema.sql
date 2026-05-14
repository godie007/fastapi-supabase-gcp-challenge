-- Align defaults and constraints with app/models/user.py
ALTER TABLE public.users
  ALTER COLUMN active SET DEFAULT true;

UPDATE public.users SET active = true WHERE active IS NULL;

ALTER TABLE public.users
  ALTER COLUMN active SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'users_role_check'
      AND conrelid = 'public.users'::regclass
  ) THEN
    ALTER TABLE public.users
      ADD CONSTRAINT users_role_check
      CHECK (role IN ('admin', 'user', 'guest'));
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS users_username_key ON public.users (username);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON public.users (email);

CREATE OR REPLACE FUNCTION public.set_users_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS users_set_updated_at ON public.users;
CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.set_users_updated_at();

COMMENT ON TABLE public.users IS 'FastAPI Users API; RLS enabled — use service_role or policies as appropriate.';
