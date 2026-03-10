// Database types
export interface Database {
  public: {
    Tables: {
      users: {
        Row: {
          id: string;
          email: string;
          name: string | null;
          avatar_url: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          email: string;
          name?: string | null;
          avatar_url?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          email?: string;
          name?: string | null;
          avatar_url?: string | null;
          updated_at?: string;
        };
      };
      content: {
        Row: {
          id: string;
          user_id: string;
          title: string;
          content: string;
          platform: string[];
          status: string;
          scheduled_at: string | null;
          published_at: string | null;
          media_urls: string[] | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          title: string;
          content: string;
          platform: string[];
          status?: string;
          scheduled_at?: string | null;
          published_at?: string | null;
          media_urls?: string[] | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          title?: string;
          content?: string;
          platform?: string[];
          status?: string;
          scheduled_at?: string | null;
          published_at?: string | null;
          media_urls?: string[] | null;
          updated_at?: string;
        };
      };
      campaigns: {
        Row: {
          id: string;
          user_id: string;
          name: string;
          description: string | null;
          status: string;
          start_date: string;
          end_date: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          name: string;
          description?: string | null;
          status?: string;
          start_date: string;
          end_date?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          name?: string;
          description?: string | null;
          status?: string;
          start_date?: string;
          end_date?: string | null;
          updated_at?: string;
        };
      };
    };
  };
}
