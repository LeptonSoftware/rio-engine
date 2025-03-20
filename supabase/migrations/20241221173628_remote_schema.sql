CREATE TRIGGER after_user_signup AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION handle_user_signup_with_invite();


