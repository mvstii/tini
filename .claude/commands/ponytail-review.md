---
description: Diff'i ve çevresindeki kodu, gerçek yükü ve güvenliği inceler (Ponytail review)
---
`@reviewer-guard` ajanını şu ek kapsamla çalıştır:
1. `git diff` yanında, değişen sembollerin **çağıranlarını ve testlerini** (`Grep`/`ast-grep`) kontrol et: kırılan çağıran, güncellenmeyen test, eksik uç durum.
2. **Gerçek yük:** döngü içi I/O, N+1, gereksiz tahsis, kilit/yarış, büyük girdide davranış.
3. **Güvenlik:** girdi doğrulama, gizli bilgi sızıntısı, enjeksiyon, yetki kontrolü.
4. Kritik/Uyarı/Öneri biçiminde ≤15 satır, her madde `dosya:satır`; sonda "Bilerek bakmadıklarım" satırı.
Ek odak: $ARGUMENTS
