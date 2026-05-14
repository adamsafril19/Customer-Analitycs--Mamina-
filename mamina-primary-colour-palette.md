# Primary Colour — Dusty Rose / Pink
**Mamina Design System v1.0**

---

## Gambaran Umum

Dusty Rose adalah warna utama (primary) brand Mamina. Warna ini dipilih karena merefleksikan kehangatan, kelembutan, dan kepercayaan — nilai-nilai yang relevan dengan audiens utama Mamina (ibu dan calon ibu). Berbeda dengan hot pink atau magenta yang agresif, dusty rose memiliki undertone abu-abu yang membuatnya terasa matang, elegan, dan tidak mencolok.

---

## Token Warna

| Token Name        | Hex       | RGB                  | HSL                  | Kegunaan Utama                         |
|-------------------|-----------|----------------------|----------------------|----------------------------------------|
| `rose-50`         | `#FDF0F3` | rgb(253, 240, 243)   | hsl(348, 75%, 97%)   | Background halaman, surface pasif      |
| `rose-100`        | `#FAD5DF` | rgb(250, 213, 223)   | hsl(345, 82%, 91%)   | Card background, hover state ringan    |
| `rose-200`        | `#F5C8D4` | rgb(245, 200, 212)   | hsl(345, 72%, 87%)   | Skeleton loader, disabled state        |
| `rose-300`        | `#EDA8BC` | rgb(237, 168, 188)   | hsl(340, 65%, 79%)   | Border ringan, divider berwarna        |
| `rose-400`        | `#E8849B` | rgb(232, 132, 155)   | hsl(344, 68%, 71%)   | Border aktif, badge background         |
| `rose-500`        | `#D95E7C` | rgb(217, 94, 124)    | hsl(344, 62%, 61%)   | Hover state tombol, ikon aktif         |
| `rose-600`        | `#C9446A` | rgb(201, 68, 106)    | hsl(342, 55%, 53%)   | **CTA button, link, focus ring**       |
| `rose-700`        | `#A8324F` | rgb(168, 50, 79)     | hsl(341, 54%, 43%)   | Tombol pressed, aksen kuat             |
| `rose-800`        | `#7D1A38` | rgb(125, 26, 56)     | hsl(341, 66%, 30%)   | Teks di atas background terang         |
| `rose-900`        | `#4F0C20` | rgb(79, 12, 32)      | hsl(340, 74%, 18%)   | Teks heading gelap, dark mode surface  |

---

## Panduan Penggunaan per Konteks

### 1. Background & Surface

```
Page background     →  rose-50  (#FDF0F3)
Card / panel        →  rose-100 (#FAD5DF)
Hover surface       →  rose-200 (#F5C8D4)
```

Gunakan `rose-50` sebagai latar halaman utama agar terasa warm tanpa terlalu terang. `rose-100` cocok untuk card yang perlu sedikit dibedakan dari background.

---

### 2. Tombol (Button)

```
Primary button (default)   →  bg: rose-600  text: white
Primary button (hover)     →  bg: rose-700  text: white
Primary button (pressed)   →  bg: rose-800  text: white
Primary button (disabled)  →  bg: rose-200  text: rose-400
```

**Contoh CSS:**
```css
.btn-primary {
  background-color: #C9446A; /* rose-600 */
  color: #FFFFFF;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
}

.btn-primary:hover {
  background-color: #A8324F; /* rose-700 */
}

.btn-primary:active {
  background-color: #7D1A38; /* rose-800 */
}

.btn-primary:disabled {
  background-color: #F5C8D4; /* rose-200 */
  color: #E8849B;            /* rose-400 */
  cursor: not-allowed;
}
```

---

### 3. Outline / Ghost Button

```
Border     →  rose-600 (#C9446A)
Text       →  rose-600 (#C9446A)
Hover bg   →  rose-50  (#FDF0F3)
```

**Contoh CSS:**
```css
.btn-outline {
  background-color: transparent;
  color: #C9446A;              /* rose-600 */
  border: 1.5px solid #C9446A;
}

.btn-outline:hover {
  background-color: #FDF0F3;   /* rose-50 */
}
```

---

### 4. Typography di atas Background Rose

| Background  | Teks Heading  | Teks Body       |
|-------------|---------------|-----------------|
| `rose-50`   | `rose-900`    | `rose-800`      |
| `rose-100`  | `rose-900`    | `rose-800`      |
| `rose-200`  | `rose-800`    | `rose-700`      |
| `rose-600`  | `#FFFFFF`     | `#FFFFFF` / `rose-100` |
| `rose-800`  | `#FFFFFF`     | `rose-100`      |

> **Penting:** Jangan gunakan warna abu-abu netral (`#333`, `#666`) di atas background rose — akan terasa dingin dan out of brand. Selalu gunakan teks dari ramp yang sama.

---

### 5. Badge & Label

```
Default badge    →  bg: rose-100  text: rose-800  border: rose-300
Active/success   →  bg: rose-600  text: white
Soft/secondary   →  bg: rose-50   text: rose-700  border: rose-200
```

**Contoh HTML + CSS:**
```html
<span class="badge-rose">New</span>
```

```css
.badge-rose {
  background-color: #FAD5DF;   /* rose-100 */
  color: #7D1A38;               /* rose-800 */
  border: 0.5px solid #EDA8BC; /* rose-300 */
  border-radius: 99px;
  font-size: 12px;
  padding: 3px 10px;
  font-weight: 500;
}
```

---

### 6. Form Elements

```
Input border (default)   →  rose-300 (#EDA8BC)
Input border (focus)     →  rose-600 (#C9446A)
Focus ring               →  rose-400 (#E8849B) at 30% opacity
Input text               →  rose-900 (#4F0C20) atau Warm Gray 900
Placeholder              →  rose-400 (#E8849B)
```

**Contoh CSS:**
```css
.input-rose {
  border: 1px solid #EDA8BC;   /* rose-300 */
  border-radius: 8px;
  padding: 10px 14px;
  color: #2E2C29;              /* Warm Gray 900 */
}

.input-rose::placeholder {
  color: #E8849B;              /* rose-400 */
}

.input-rose:focus {
  outline: none;
  border-color: #C9446A;       /* rose-600 */
  box-shadow: 0 0 0 3px rgba(232, 132, 155, 0.3); /* rose-400 30% */
}
```

---

### 7. Link

```
Default     →  rose-600 (#C9446A)
Hover       →  rose-700 (#A8324F) + underline
Visited     →  rose-800 (#7D1A38)
```

---

### 8. Divider & Border

```
Subtle divider   →  rose-100 (#FAD5DF)
Default border   →  rose-200 (#F5C8D4)
Emphasis border  →  rose-300 (#EDA8BC)
Active border    →  rose-600 (#C9446A)
```

---

## Aksesibilitas (WCAG Contrast)

| Kombinasi                              | Rasio Kontras | WCAG Level  |
|----------------------------------------|---------------|-------------|
| `rose-600` teks di atas `white`        | 4.6 : 1       | ✅ AA       |
| `rose-800` teks di atas `rose-50`      | 7.2 : 1       | ✅ AAA      |
| `white` teks di atas `rose-600`        | 4.6 : 1       | ✅ AA       |
| `white` teks di atas `rose-700`        | 6.1 : 1       | ✅ AA Large |
| `rose-400` teks di atas `white`        | 2.8 : 1       | ⚠️ AA Gagal (hanya dekoratif) |
| `rose-900` teks di atas `rose-50`      | 13.1 : 1      | ✅ AAA      |

> **Aturan:** Gunakan minimum `rose-600` untuk teks interaktif di atas background putih/terang. Hindari `rose-300` atau `rose-400` sebagai warna teks utama.

---

## Kombinasi dengan Warna Lain di Sistem Mamina

| Pasangan                       | Konteks                                    |
|--------------------------------|--------------------------------------------|
| Rose + Ivory (Cream)           | Layout utama, halaman produk               |
| Rose + Warm Gray               | Teks body, form, tabel data                |
| Rose + Sage Green              | Rose = primary action, Sage = success/safe |
| Rose-50 + Rose-600             | Card dengan tombol CTA                     |
| Rose-800 + Ivory-50            | Header gelap dengan background terang      |

---

## Variabel CSS (Design Token)

Tambahkan ini ke `:root` di file CSS global:

```css
:root {
  --color-rose-50:  #FDF0F3;
  --color-rose-100: #FAD5DF;
  --color-rose-200: #F5C8D4;
  --color-rose-300: #EDA8BC;
  --color-rose-400: #E8849B;
  --color-rose-500: #D95E7C;
  --color-rose-600: #C9446A;
  --color-rose-700: #A8324F;
  --color-rose-800: #7D1A38;
  --color-rose-900: #4F0C20;

  /* Alias semantik */
  --color-primary:          var(--color-rose-600);
  --color-primary-hover:    var(--color-rose-700);
  --color-primary-active:   var(--color-rose-800);
  --color-primary-subtle:   var(--color-rose-50);
  --color-primary-border:   var(--color-rose-300);
  --color-primary-text:     var(--color-rose-800);
}
```

---

## Tailwind CSS Config (Opsional)

Jika menggunakan Tailwind, tambahkan ke `tailwind.config.js`:

```js
module.exports = {
  theme: {
    extend: {
      colors: {
        rose: {
          50:  '#FDF0F3',
          100: '#FAD5DF',
          200: '#F5C8D4',
          300: '#EDA8BC',
          400: '#E8849B',
          500: '#D95E7C',
          600: '#C9446A',
          700: '#A8324F',
          800: '#7D1A38',
          900: '#4F0C20',
        },
      },
    },
  },
}
```

---

*Mamina Design System — Primary Colour Documentation*  
*Last updated: Mei 2026*
