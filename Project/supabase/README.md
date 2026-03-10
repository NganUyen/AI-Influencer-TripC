# Supabase Configuration

This directory contains Supabase database schemas, migrations, and configurations.

## Structure

```
supabase/
├── migrations/        # Database migration SQL files
├── schema.sql        # Complete database schema
└── seed.sql          # Seed data for development
```

## Database Schema

The database includes the following main tables:

- **users** - User accounts and profiles
- **content** - Generated content items
- **campaigns** - Marketing campaigns
- **personas** - AI influencer personas
- **media_assets** - Generated media files
- **workflows** - Temporal workflow tracking
- **social_accounts** - Connected social media accounts
- **engagement_actions** - Tracking engagement syndicate actions

## Running Migrations

If using Supabase CLI:

```bash
supabase db push
```

Or apply migrations manually through Supabase Dashboard SQL Editor.

## Local Development

For local Supabase instance:

```bash
supabase start
supabase db reset
```
