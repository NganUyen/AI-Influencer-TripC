-- Seed data for development and testing

-- Insert test user
INSERT INTO public.users (id, email, name) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'demo@aiinfluencer.com', 'Demo User')
ON CONFLICT (id) DO NOTHING;

-- Insert test campaign
INSERT INTO public.campaigns (id, user_id, name, description, status, start_date) VALUES
    ('660e8400-e29b-41d4-a716-446655440000', '550e8400-e29b-41d4-a716-446655440000', 'Launch Campaign', 'Initial product launch campaign', 'active', NOW())
ON CONFLICT (id) DO NOTHING;

-- Insert test persona
INSERT INTO public.personas (id, user_id, name, description, voice_profile, platforms, is_active) VALUES
    ('770e8400-e29b-41d4-a716-446655440000', '550e8400-e29b-41d4-a716-446655440000', 'TechGuru AI', 'Expert in tech and innovation', 'Professional, informative, engaging', ARRAY['twitter', 'linkedin'], true)
ON CONFLICT (id) DO NOTHING;

-- Insert test content
INSERT INTO public.content (id, user_id, campaign_id, title, content, platform, status) VALUES
    ('880e8400-e29b-41d4-a716-446655440000', '550e8400-e29b-41d4-a716-446655440000', '660e8400-e29b-41d4-a716-446655440000', 'Welcome Post', 'Excited to announce our new AI-driven platform! 🚀', ARRAY['twitter', 'linkedin'], 'draft')
ON CONFLICT (id) DO NOTHING;
