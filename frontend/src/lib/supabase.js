/**
 * supabase.js
 *
 * Initializes and exports the Supabase client for use throughout the frontend.
 * Reads VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY from environment variables.
 * This is the single source of truth for the Supabase connection in the frontend.
 *
 * Usage: import { supabase } from '@/lib/supabase'
 */

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
