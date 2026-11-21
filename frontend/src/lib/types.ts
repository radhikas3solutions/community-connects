// Mirrors backend/app/schemas. Keep in sync (or generate from /openapi.json later).

export type Language = "en" | "te";
export type UserRole = "user" | "business" | "moderator" | "admin";
export type CategoryKind = "marketplace" | "business" | "community";
export type ListingType = "sell" | "buy" | "free";
export type ListingStatus = "draft" | "pending_review" | "active" | "sold" | "removed";
export type ItemCondition = "new" | "like_new" | "good" | "fair" | "for_parts";

export interface ListingImage {
  id: string;
  /** Signed, expiring URL: don't persist it. */
  url: string;
  width: number;
  height: number;
}

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
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  phone: string | null;
  whatsapp: string | null;
  avatar_url: string | null;
  preferred_language: Language;
  role: UserRole;
  city: string | null;
  zip_code: string | null;
  whatsapp_opt_in: boolean;
  created_at: string;
}

export interface AdminProfile extends Profile {
  is_banned: boolean;
}

export interface Listing {
  id: string;
  listing_type: ListingType;
  status: ListingStatus;
  condition: ItemCondition | null;
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
  images: ListingImage[];
  ai_confidence: number | null;
  ai_price_low_cents: number | null;
  ai_price_high_cents: number | null;
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

/** Error body from the API: `detail` is a string, or `{code, message}` on photo/AI routes. */
export type ApiErrorDetail = string | { code: string; message: string };

export type EntryKind = "business" | "individual";
export type DirectoryStatus = "pending_review" | "active" | "rejected" | "removed";

export interface MenuItem {
  id: string | null;
  section: string | null;
  name: string;
  name_te: string | null;
  description: string | null;
  price_cents: number | null;
  is_vegetarian: boolean | null;
}

export interface Business {
  id: string;
  kind: EntryKind;
  status: DirectoryStatus;
  name: string;
  name_te: string | null;
  description_en: string | null;
  description_te: string | null;
  phone: string | null;
  whatsapp: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  city: string | null;
  zip_code: string | null;
  service_area: string | null;
  hours: string | null;
  languages: string[];
  is_verified: boolean;
  source: string | null; // imported from public data: "npi" = NPI Registry, "osm" = OpenStreetMap
  source_url?: string | null; // the OpenStreetMap record (attribution, and where to fix it)
  specialty?: string | null; // imported entries: "Endocrinologist", "Indian · Restaurant" (English)
  category: Category | null;
  menu: MenuItem[];
  /** An individual's phone/email withheld from a signed-out visitor. */
  contact_hidden: boolean;
  can_edit: boolean;
  review_note: string | null;
  created_at: string;
  updated_at: string;
}
