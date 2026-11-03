---
name: ui-design-efficiency
description: Arayüz/stil işlerinde (CSS, XAML, TSX/Vue, tema, bileşen) token tasarrufu ve tasarım sistemi disiplini; hardcoded renk/boyut yasağı, mevcut token ve bileşenleri yeniden kullanma, cerrahi stil düzenlemesi.
paths:
  - "**/*.{css,scss,sass,less}"
  - "**/*.{xaml,axaml,razor}"
  - "**/*.{tsx,jsx,vue,svelte}"
---
# UI / TASARIM VERİMLİLİĞİ

Yalnızca arayüz, stil veya tema dosyasına dokunan görevlerde uygula.

## Keşif (ana bağlamı şişirme)
- Ekran görüntüsü, tasarım dışa aktarımı (görsel/JSON), büyük CSS/XAML/UI ağacı ve "mevcut token/renk/bileşen envanteri" taraması `@gemini-scout`'a gider; sonuç `SPEC.md`'ye "kullanılacak mevcut token/bileşenler: ad, dosya:satır" olarak yazılır.
- Stil dosyasını baştan sona okuma: `Grep` ile seçici/değişken/bileşen adını bul, yalnızca o bloğu oku.

## Yazım kuralları
1. **Hardcoded değer yok:** satır içi hex/rgb/px yazma; mevcut tasarım token'ını, tema değişkenini veya bileşeni kullan (CSS değişkeni, XAML ResourceDictionary, tema nesnesi).
2. **Yeniden kullan:** aynı stili ikinci kez yazma; mevcut bileşeni/sınıfı genişlet. Yeni token gerekiyorsa tek yerde (token dosyasında) tanımla, sonra referans ver.
3. **Cerrahi düzenle:** tüm UI dosyasını yeniden yazma; yalnızca ilgili bileşen/stil bloğunu değiştir.
4. **Erişilebilirlik:** metin/arka plan kontrastı, odak durumu, etiket/alt metin, klavye erişimi bozulmasın.
5. **Maliyet:** gereksiz iç içe yerleşim, tekrar render/layout tetikleyen değişiklikten kaçın.

## Kontrol
- Düzenleme sonrası diff'te yeni hex/px var mı bak; varsa token'a çevir. Denetim `@reviewer-guard` tarafından da yapılır.
