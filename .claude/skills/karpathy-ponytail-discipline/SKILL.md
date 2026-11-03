---
name: karpathy-ponytail-discipline
description: Kod yazarken/düzenlerken uygulanan mühendislik disiplini (Karpathy 4 prensip + Ponytail "en küçük eksiksiz değişiklik"); yanıt sonunda atlananları ve kalan riskleri bildirir.
---
# KOD DİSİPLİNİ (Karpathy + Ponytail)

## Karpathy 4 prensip
1. **Önce düşün:** Varsayımları ve belirsizlikleri kodlamadan önce 1-3 cümleyle yaz. Belirsizlik sonucu değiştiriyorsa sor; değiştirmiyorsa makul varsayımla ilerle ve belirt.
2. **Önce yalınlık (YAGNI):** İstenmeyen soyutlama, parametre, yapılandırma ve "ileride lazım olur" kodu ekleme.
3. **Cerrahi değişiklik:** İlgisiz satıra, biçimlendirmeye, yeniden adlandırmaya dokunma. Her değişen satır isteğe bağlanabilmeli.
4. **Hedef odaklı doğrulama:** Değişikliği en küçük ilgili testle/derlemeyle doğrulamadan "bitti" deme. Doğrulanamadıysa bunu söyle.

## Ponytail: en küçük EKSİKSİZ değişiklik
"En az satır" değil, "yarım bırakmayan en küçük değişiklik". Yazmadan önce `Grep`/`ast-grep` ile haritala:
- Değiştirilen sembolün **çağıranları**
- Etkilenen **testler** (güncelle veya ekle)
- Kırabilecek **diğer noktalar** (arayüz uygulayıcıları, serileştirme, yapılandırma, dokümantasyon)

## Yanıt sonu (zorunlu, ≤3 satır)
- **Bilerek atladıklarım:** ...
- **Kalan riskler:** ... (yoksa "yok")
