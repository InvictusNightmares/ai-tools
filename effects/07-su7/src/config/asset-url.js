// The standalone build supplies this JSON block before the application script.
// Regular Vite builds keep loading assets from public/ as usual.
const embeddedElement = document.getElementById("su7-embedded-assets");
const embeddedAssets = embeddedElement ? JSON.parse(embeddedElement.textContent) : null;
const objectURLs = new Map();
embeddedElement?.remove();

export function resolveAssetURL(url) {
  if (!embeddedAssets) return url;

  const key = url.replace(/^\.\//, "");
  const asset = embeddedAssets[key];
  if (!asset) throw new Error(`Missing embedded asset: ${key}`);

  if (!objectURLs.has(key)) {
    const binary = atob(asset.base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: asset.type });
    // Keep the filename extension for the engine and audio loader's dispatch.
    // Object URLs live for the document lifetime and need no network access.
    objectURLs.set(key, `${URL.createObjectURL(blob)}#${key.split("/").pop()}`);
    delete asset.base64;
  }
  return objectURLs.get(key);
}
