// Book Two v2: two-sided leaves start at PDF page 3 (one-based PDF numbering).
// Shared by validation and the renderer; changing edition requires a new adapter.
export function bookSpread(pdfPage) {
 if(!Number.isInteger(pdfPage)||pdfPage<3||pdfPage>146)return null;
 return Math.floor((pdfPage-2)/2);
}
