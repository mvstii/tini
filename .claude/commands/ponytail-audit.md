---
description: Tüm repoyu haritalayıp sorunları önceliklendirir, çıktıyı SPEC.md'ye yazar (Ponytail audit)
---
`@gemini-scout` ajanıyla (10+ dosya taraması; Seviye 2) repoyu haritala ve `SPEC.md` içine yaz:
1. Modül/bağımlılık haritası (kısa).
2. Sorunlar, **Yüksek/Orta/Düşük** önceliğiyle: güvenlik, test boşlukları, ölü kod, kırılgan noktalar. Her madde `dosya:satır` + 1 cümle etki.
3. İlk 5 sorun için en küçük eksiksiz düzeltme önerisi.
Kod değiştirme; yalnızca raporla. Kapsam: $ARGUMENTS (boşsa tüm repo).
