# portfolio.json: המבנה (בשבילי)

הקובץ יושב ב-`פרויקטים/תיק עבודות/`, ליד `inventory.json`. ממנו `build.mjs` בונה את ה-PDF.

```json
{
  "studio": "תכלת",
  "tagline": "סטודיו לעיצוב גרפי לשמחות ולעסקים קטנים",
  "year": "תשפ״ז",
  "about": ["משפט ראשון.", "משפט שני.", "משפט שלישי."],
  "language": "השפה העיצובית במשפט אחד",
  "email": "studio@example.com",
  "example": true,
  "bsd": true,
  "pages": [
    { "type": "work", "media": "media/07.jpg", "title": "הזמנה לבר מצווה", "kind": "הזמנה · A5 · לבית דפוס", "caption": "משפט או שניים." },
    { "type": "pair", "works": [
      { "media": "media/02.jpg", "title": "...", "kind": "...", "caption": "..." },
      { "media": "media/04.jpg", "title": "...", "kind": "...", "caption": "..." }
    ] },
    { "type": "video", "media": "media/10.jpg", "title": "הסטודיו פתוח", "kind": "פרסומת וידאו · רוחבי", "duration": "0:13", "caption": "..." }
  ]
}
```

- **השדות `media` ו-`duration`:** מעתיקים אותם מ-`inventory.json`, כלומר `items[].media` ו-`items[].duration`. לא כותבים נתיב בעצמי.
- **עמודים אוטומטיים:** השער, "על הסטודיו" (מופיע רק אם יש `about`) ויצירת הקשר נבנים לבד. לא כותבים אותם ב-`pages`.
- **`example: true`:** מוסיף "פרטים לדוגמה" מתחת למייל.
- **`bsd: false`:** מוריד את בס״ד.
- **אפשר לדרוס:** `paper`, `ink`, `accent` (צבעים), `headFont` ו-`bodyFont` (רק משמות הגופנים שבסקיל), `contactTitle` ו-`contactLine`.
- **`palette`:** עד 5 צבעים לעמוד "על הסטודיו". בלי השדה הזה, הצבעים נלקחים מ-`brand.md`.
- **אורך:** בדרך כלל 6–10 עבודות, וכך 7–11 עמודים. יותר מזה מתיש. תיק עבודות טוב בוחר.
