-- Development seed data for the current product surface.
-- Apply only to disposable local/dev databases after schema.sql.

INSERT INTO public.users (id, email, name)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'persona-system@local.ai-influencer.invalid', 'Persona System'),
    ('550e8400-e29b-41d4-a716-446655440000', 'demo@aiinfluencer.com', 'Demo User')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.brand_profiles (
    id,
    user_id,
    product_name,
    website_url,
    audience,
    offer_summary,
    tone_voice,
    campaign_goals,
    asset_urls,
    timezone,
    posting_cadence,
    approval_preferences,
    telegram_contact,
    onboarding_status
)
VALUES (
    '560e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440000',
    'TripC Studio',
    'https://tripc.ai',
    'Travel operators and tourism teams',
    'AI-assisted media planning and campaign execution',
    'clear and practical',
    '["launch","signups"]'::jsonb,
    '["https://cdn.example.com/tripc/logo.png"]'::jsonb,
    'UTC',
    '{"weekly_posts": 3, "best_days": ["Tuesday", "Thursday"]}'::jsonb,
    '{"mode": "review_first"}'::jsonb,
    '@tripc',
    'completed'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.personas (
    id,
    user_id,
    name,
    description,
    voice_profile,
    platforms,
    is_active,
    persona_id,
    display_name,
    language,
    tts_voice,
    avatar_image_url,
    status,
    video_count,
    tone_default,
    market_default,
    thumbnail_url
)
VALUES (
    '770e8400-e29b-41d4-a716-446655440000',
    '00000000-0000-0000-0000-000000000001',
    'TripC Host',
    'Travel-industry explainer persona for demos',
    'Professional and friendly',
    ARRAY['linkedin', 'youtube'],
    TRUE,
    'demo-travel-host',
    'Demo Travel Host',
    'English',
    'alloy',
    'https://cdn.example.com/tripc/persona-avatar.png',
    'draft',
    0,
    'clear',
    'travel',
    'https://cdn.example.com/tripc/persona-thumb.png'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.personas (
    id,
    user_id,
    name,
    description,
    voice_profile,
    platforms,
    is_active,
    persona_id,
    display_name,
    language,
    tts_voice,
    avatar_source_type,
    avatar_prompt,
    status,
    video_count,
    tone_default,
    market_default
)
VALUES
    (
        '77111111-1111-4111-8111-111111111111',
        '00000000-0000-0000-0000-000000000001',
        'Alex Rivera',
        'US English reviewer for North American app and lifestyle campaigns.',
        'Confident and polished',
        ARRAY['tiktok', 'instagram', 'youtube'],
        TRUE,
        'global-us-alex',
        'Alex Rivera',
        'English (US)',
        'en-US-Standard-F',
        'fal_ai',
        'Photorealistic studio headshot of Alex Rivera, globally appealing U.S. tech and lifestyle creator, confident expression, smart casual wardrobe, direct gaze, clean soft lighting, neutral backdrop, cinematic detail.',
        'draft',
        0,
        'confident',
        'united_states'
    ),
    (
        '77222222-2222-4222-8222-222222222222',
        '00000000-0000-0000-0000-000000000001',
        'Wei Chen',
        'Mandarin reviewer for China-focused consumer app and lifestyle campaigns.',
        'Measured and modern',
        ARRAY['tiktok', 'instagram', 'youtube'],
        TRUE,
        'global-cn-wei',
        'Wei Chen',
        'Mandarin',
        'cmn-CN-Standard-B',
        'fal_ai',
        'Photorealistic studio headshot of Wei Chen, Mandarin-speaking creator for China market, polished modern wardrobe, calm confident expression, direct gaze, soft editorial lighting, neutral backdrop, cinematic detail.',
        'draft',
        0,
        'measured',
        'china'
    ),
    (
        '77333333-3333-4333-8333-333333333333',
        '00000000-0000-0000-0000-000000000001',
        'Natasha Volkov',
        'Russian reviewer for Eastern Europe-focused app and travel campaigns.',
        'Direct and composed',
        ARRAY['tiktok', 'instagram', 'youtube'],
        TRUE,
        'global-ru-natasha',
        'Natasha Volkov',
        'Russian',
        'ru-RU-Standard-C',
        'fal_ai',
        'Photorealistic studio headshot of Natasha Volkov, Russian-speaking lifestyle reviewer, poised confident expression, contemporary city style, direct gaze, soft studio lighting, neutral backdrop, cinematic detail.',
        'draft',
        0,
        'direct',
        'russia'
    ),
    (
        '77444444-4444-4444-8444-444444444444',
        '00000000-0000-0000-0000-000000000001',
        'Arjun Sharma',
        'Indian English reviewer for India-focused mobile app and lifestyle campaigns.',
        'Upbeat and clear',
        ARRAY['tiktok', 'instagram', 'youtube'],
        TRUE,
        'global-in-arjun',
        'Arjun Sharma',
        'Indian English',
        'en-IN-Standard-D',
        'fal_ai',
        'Photorealistic studio headshot of Arjun Sharma, Indian English creator for India market, upbeat confident expression, modern casual blazer, direct gaze, soft studio lighting, neutral backdrop, cinematic detail.',
        'draft',
        0,
        'upbeat',
        'india'
    ),
    (
        '77555555-5555-4555-8555-555555555555',
        '00000000-0000-0000-0000-000000000001',
        'Valeria Cruz',
        'Mexican Spanish reviewer for Mexico-focused mobile app campaigns.',
        'Warm and persuasive',
        ARRAY['tiktok', 'instagram', 'youtube'],
        TRUE,
        'global-mx-valeria',
        'Valeria Cruz',
        'Mexican Spanish',
        'es-US-Standard-B',
        'fal_ai',
        'Photorealistic studio headshot of Valeria Cruz, Mexican Spanish creator for Mexico market, warm confident expression, stylish casual wardrobe, direct gaze, soft studio lighting, neutral backdrop, cinematic detail.',
        'draft',
        0,
        'warm',
        'mexico'
    )
ON CONFLICT (user_id, persona_id) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    voice_profile = EXCLUDED.voice_profile,
    platforms = EXCLUDED.platforms,
    is_active = EXCLUDED.is_active,
    display_name = EXCLUDED.display_name,
    language = EXCLUDED.language,
    tts_voice = EXCLUDED.tts_voice,
    avatar_source_type = EXCLUDED.avatar_source_type,
    avatar_prompt = EXCLUDED.avatar_prompt,
    tone_default = EXCLUDED.tone_default,
    market_default = EXCLUDED.market_default,
    updated_at = NOW();

INSERT INTO public.social_accounts (
    id,
    user_id,
    platform,
    account_name,
    account_handle,
    is_primary,
    is_active,
    connection_status,
    display_name,
    connection_method,
    scopes,
    publish_capabilities
)
VALUES (
    '570e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440000',
    'linkedin',
    'TripC Company',
    'tripc',
    TRUE,
    TRUE,
    'connected',
    'TripC Company',
    'oauth',
    ARRAY['openid', 'profile', 'w_member_social'],
    '{"post": true, "analytics": true}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.assistant_threads (
    id,
    user_id,
    title,
    status,
    last_message_preview
)
VALUES (
    '580e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440000',
    'Launch Planning',
    'active',
    'Use a review-first launch sequence'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.assistant_messages (
    id,
    thread_id,
    role,
    content,
    metadata
)
VALUES
    (
        '581e8400-e29b-41d4-a716-446655440000',
        '580e8400-e29b-41d4-a716-446655440000',
        'user',
        'Plan a launch week for TripC Studio.',
        '{"source": "seed"}'::jsonb
    ),
    (
        '582e8400-e29b-41d4-a716-446655440000',
        '580e8400-e29b-41d4-a716-446655440000',
        'assistant',
        'Start with a review-first campaign, then stage platform-specific posts for the connected LinkedIn account.',
        '{"source": "seed"}'::jsonb
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.assistant_artifacts (
    id,
    thread_id,
    artifact_type,
    title,
    payload
)
VALUES (
    '583e8400-e29b-41d4-a716-446655440000',
    '580e8400-e29b-41d4-a716-446655440000',
    'plan_snapshot',
    'Seed strategy snapshot',
    '{"target_platforms": ["linkedin"], "content_pillars": ["product launch", "customer proof"]}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.campaigns (
    id,
    user_id,
    name,
    description,
    status,
    start_date,
    end_date,
    brand_profile_id,
    plan_status,
    approval_status,
    target_platforms,
    connected_account_ids,
    plan_data,
    artifact_summary
)
VALUES (
    '660e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440000',
    'Launch Campaign',
    'Initial product launch campaign',
    'draft',
    NOW(),
    NOW() + INTERVAL '7 days',
    '560e8400-e29b-41d4-a716-446655440000',
    'draft',
    'pending',
    ARRAY['linkedin'],
    ARRAY['570e8400-e29b-41d4-a716-446655440000']::uuid[],
    '{"content_pillars": ["launch", "education"], "approval_mode": "review_first"}'::jsonb,
    '{"source_thread_id": "580e8400-e29b-41d4-a716-446655440000"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.content (
    id,
    user_id,
    campaign_id,
    title,
    content,
    platform,
    status,
    scheduled_at
)
VALUES (
    '880e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440000',
    '660e8400-e29b-41d4-a716-446655440000',
    'Welcome Post',
    'Introducing TripC Studio with a review-first AI marketing workflow.',
    ARRAY['linkedin'],
    'scheduled',
    NOW() + INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.media_assets (
    id,
    user_id,
    persona_id,
    url,
    source_url,
    type,
    filename,
    bucket_name,
    storage_path,
    size,
    mime_type,
    metadata
)
VALUES (
    '990e8400-e29b-41d4-a716-446655440000',
    '00000000-0000-0000-0000-000000000001',
    'demo-travel-host',
    'https://cdn.example.com/media/users/00000000-0000-0000-0000-000000000001/personas/demo-travel-host/image/2026-03/avatar.png',
    'https://fal.example.com/generated/demo-travel-host-avatar.png',
    'image',
    'users/00000000-0000-0000-0000-000000000001/personas/demo-travel-host/image/2026-03/avatar.png',
    'media',
    'users/00000000-0000-0000-0000-000000000001/personas/demo-travel-host/image/2026-03/avatar.png',
    182044,
    'image/png',
    '{"seed": true, "owner_key": "demo-seed", "generation_prompt": "demo persona avatar"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.telegram_subscribers (
    chat_id,
    chat_type,
    username,
    first_name,
    role,
    is_active
)
VALUES (
    1000001,
    'private',
    'demo_operator',
    'Demo',
    'ADMIN',
    TRUE
)
ON CONFLICT (chat_id) DO NOTHING;
