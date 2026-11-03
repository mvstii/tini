---
name: git-worktree
description: Paralel alt ajan veya oturumlarda çakışmayı önleyen worktree kuralları (yerleşik isolation worktree ile).
---
# PARALEL ÇALIŞMA: WORKTREE KURALLARI

Mekanizma yerleşik: Agent çağrısında `isolation: "worktree"`, oturumda `EnterWorktree` / `claude -w`. Elle `git worktree add` gerekmez. Kurallar:
- Worktree üst oturumun HEAD'inden değil varsayılan daldan açılır; commit edilmemiş değişiklikler ve `SPEC.md` görünmez. `SPEC.md` içeriğini çağrı istemine göm.
- Ajanların dosya kümeleri ayrık olmalı (örn. `src/api/**` ve `src/ui/**`); çakışan dosya varsa paralel çalıştırma.
- Sonuç her worktree'nin dalındadır; testler geçtikten sonra elle birleştir (`git merge`). Değişiklik yapılmayan worktree kendiliğinden temizlenir.
- `isolation`'ı ajan frontmatter'ına KOYMA; seri SPEC → uygula → test zincirini bozar. Çağrı başına ver.
- Worktree oturumlarında `CLAUDE_PROJECT_DIR` ana depodur (kancalar oradan çalışır).
