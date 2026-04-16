-- Allow transient setup state while Fal/HeyGen avatar provisioning is in flight.

ALTER TABLE public.personas
    DROP CONSTRAINT IF EXISTS personas_status_check;

ALTER TABLE public.personas
    ADD CONSTRAINT personas_status_check
    CHECK (
        status = ANY (
            ARRAY[
                'draft'::text,
                'generating'::text,
                'ready'::text,
                'failed'::text,
                'archived'::text
            ]
        )
    );
