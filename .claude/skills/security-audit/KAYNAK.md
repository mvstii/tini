# Kaynak

- Depo: https://github.com/cloudflare/security-audit-skill
- Sabitlenen commit: `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` (2026-09-14)
- Lisans: MIT (`LICENSE`, Cloudflare)
- Alınan: `skills/security-audit/` altındaki `.md` dosyaları, `report-schema.json`, `validate-findings.cjs`,
  `validate-coverage-ledger.cjs`. Alınmayan: `*.test.cjs`.
- Aegis değişiklikleri: SKILL.md frontmatter'ına `disable-model-invocation: true` ve `argument-hint`,
  başlığın altına AEGIS.md yönlendirmesi. Diğer dosyalar özgün haliyle duruyor.
- Güncellemek için: yeni commit'i inceleyin, dosyaları yeniden kopyalayın, iki SKILL.md değişikliğini tekrar
  uygulayın, bu dosyadaki SHA'yı değiştirin ve `bash .claude/scripts/test-guards.sh` çalıştırın.
