# Übersicht: Datenbank-Wiederherstellung

Tags: #datenbank #handbuch

## Zweck

Diese Notiz beschreibt, wie wir eine PostgreSQL-Datenbank nach einem Ausfall wiederherstellen. Sie richtet sich an
alle Entwicklerinnen und Entwickler im Bereitschaftsdienst. Die Größe der Datenbank beträgt etwa 400 GB, daher
dauert eine vollständige Wiederherstellung ungefähr 90 Minuten.

## Häufige Fragen

### Wann ist eine Wiederherstellung nötig?

Wenn Daten versehentlich gelöscht wurden oder der Primärknoten nicht mehr erreichbar ist und die Replikate zu
weit zurückliegen. Bei einem einfachen Neustart ist keine Wiederherstellung erforderlich.

### Wer entscheidet über die Wiederherstellung?

Die Bereitschaftsleitung entscheidet gemeinsam mit der Datenbankverantwortlichen. Der Beschluss wird im
Störungsprotokoll festgehalten.

## Schritte

1. Zuerst den letzten Schnappschuss prüfen: `aws rds describe-db-snapshots --db-instance-identifier bestellungen`
2. Den Schnappschuss in eine neue Instanz wiederherstellen.
3. Die Anwendung auf die neue Instanz umstellen (Verbindungszeichenfolge im Geheimnisspeicher ändern).

```bash
# Wiederherstellung auf einen bestimmten Zeitpunkt
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier bestellungen \
  --target-db-instance-identifier bestellungen-wiederhergestellt \
  --restore-time 2025-03-04T09:00:00Z
```

## Donaudampfschifffahrtsgesellschaftskapitänsmützenverzeichnis

Ein absichtlich langes Wort, damit die Zerlegung auch mit deutschen Komposita getestet wird: Rindfleischetikettierungsüberwachungsaufgabenübertragungsgesetz.
