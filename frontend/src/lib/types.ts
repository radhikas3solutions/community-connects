// Mirrors backend/app/schemas. Keep in sync (or generate from /openapi.json later).

export type Language = "en" | "te";
export type UserRole = "user" | "business" | "moderator" | "admin";
export type CategoryKind = "marketplace" | "business" | "community";
export type ListingType = "sell" | "buy" | "free";
export type ListingStatus = "draft" | "pending_review" | "active" | "sold" | "removed";

export interface Category {
  id: number;
  slug: string;
  kind: CategoryKind;
  name_en: string;
  name_te: string;
  icon: string | null;
  parent_id: number | null;
  is_community_specific: boolean;
}

export interface Profile {
  id: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  preferred_language: Language;
  role: UserRole;
  city: string | null;
  zip_code: string | null;
  whatsapp_opt_in: boolean;
  created_at: string;
}

export interface Listing {
  id: string;
  listing_type: ListingType;
  status: ListingStatus;
  condition: string | null;
  source_language: Language;
  title_en: string | null;
  title_te: string | null;
  description_en: string | null;
  description_te: string | null;
  price_cents: number | null;
  currency: string;
  is_negotiable: boolean;
  city: string | null;
  zip_code: string | null;
  location: { lat: number; lng: number } | null;
  distance_km: number | null;
  category: Category | null;
  owner: { id: string; display_name: string | null; avatar_url: string | null; city: string | null };
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
