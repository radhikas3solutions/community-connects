const MAX_DIMENSION = 2048;
const QUALITY = 0.85;

/**
 * Shrinks a photo in the browser before upload: a 12 MP phone photo (4-8 MB) becomes a
 * ~500 KB JPEG, which matters on mobile data. Re-encoding through a canvas also drops EXIF
 * (including GPS) before the photo leaves the device; the server strips it again regardless.
 *
 * Falls back to the original file if the browser can't decode it (the server then decides).
 */
export async function resizeForUpload(file: File): Promise<File> {
  if (!file.type.startsWith("image/")) return file;
  try {
    // Applies EXIF orientation, so portrait phone photos stay upright.
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.fillStyle = "#fff"; // transparent PNGs become white, not black
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close();

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY));
    if (!blob) return file;
    const name = file.name.replace(/\.[^.]+$/, "") || "photo";
    return new File([blob], `${name}.jpg`, { type: "image/jpeg" });
  } catch {
    return file;
  }
}
