# MobaXterm SSH for GitHub Copilot

Denne SKILL-en hjelper Copilot med å bruke MobaXterm-installasjonen og de
lagrede SSH-forbindelsene på din egen Windows-PC. Du trenger ikke beskrive
hvordan SSH, Bash eller autentisering fungerer.

## Installering

1. Pakk ut mappen `mobaxterm-bash-ssh` fra ZIP-filen.
2. Legg hele mappen i `%USERPROFILE%\.copilot\skills\`. Resultatet skal være
   `%USERPROFILE%\.copilot\skills\mobaxterm-bash-ssh\SKILL.md`, ikke en ekstra
   mappe mellom `mobaxterm-bash-ssh` og `SKILL.md`.
3. Start en ny Copilot-chat. Ved behov, be eksplisitt om å bruke
   `mobaxterm-bash-ssh`. Klienten må støtte Agent Skills og ha tilgang til
   lokal kommandokjøring på Windows.

For bruk bare i ett prosjekt kan mappen i stedet ligge under
`.github\skills\mobaxterm-bash-ssh\` i prosjektet. Ikke installer begge steder
med forskjellige versjoner.

SKILL-en installerer ikke MobaXterm, importerer ikke andres sesjoner og gir
ikke Copilot flere rettigheter enn klienten ellers tillater.

## Før første tilkobling

Åpne MobaXterm som vanlig. Bruk din egen bruker, og la programmet stå åpent.
Hvis passordlageret er låst, lås det opp i MobaXterm, aldri i chatten.
Forbindelsen må allerede fungere for deg. Copilot finner den lokale
installasjonsstien; du trenger ikke bruke forfatterens mapper.

## Eksempler på korte meldinger

Se [PROMPT.md](PROMPT.md) for en detaljert, kopierbar statusprompt med
verktøyvalg, avgrensning og stoppregler. Bytt ut sesjonsnavn og plattform
med dine egne opplysninger før du bruker den.

- "Bruk MobaXterm og sjekk diskplassen på serveren drift-linux."
- "Koble til sesjonen lab-switch og vis modell og programvareversjon."
- "Finn MobaXterm-installasjonen min, men ikke koble til noe."
- "SSH virker ikke til drift-linux. Bruk MobaXterm og finn hvor det stopper."

Bruk dine egne faktiske server-/sesjonsnavn. Dersom flere sesjoner passer,
skal Copilot spørre hvilken du mener. Dersom det kommer en passordprompt eller
en ukjent vertsnøkkel, skal Copilot stoppe og forklare hva du må avklare,
ikke prøve mange ganger.

## Hva som følger med

`SKILL.md` er arbeidsoppskriften for Copilot. `references\operations.md`
dekker avansert feilsøking. `scripts\` inneholder en valgfri lokal
switch-emulator for utvikling av Expect-tester. Den er ikke nødvendig for
vanlig SSH og bruker bare en syntetisk testkonto.

Vanlig bruk krever ingen Python-pakker. Emulatoren krever Windows Python
3.10+ og Paramiko 5.0.0; Expect-klienten krever MobaXterms Expect
(tidligere testet med 5.45). Ikke installer emulatoravhengigheter bare for å
koble til en server.

ZIP-utgaven inneholder ikke forfatterens virkelige testverter,
personlige filstier, fingeravtrykk, sesjonsfiler eller historiske logger.
Den sender ingenting til andre personer eller tjenester.
