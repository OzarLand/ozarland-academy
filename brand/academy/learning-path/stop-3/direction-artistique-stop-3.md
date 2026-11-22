# Direction artistique — Étape 3 « Operate — Kolla-Ansible Academy »

**Statut :** plan validé, prompts prêts ; aucune image n’est générée dans ce lot. Les images restent `prompt-only` jusqu’à leur production et leur contrôle.

## Intention

L’étape 3 est l’atelier-bibliothèque de l’île. En plein jour, les parchemins aux marques abstraites, les maquettes de serveurs en laiton et l’établi de lecture donnent une place visible à l’étude du code source. L’accent est le bois `#C4904F`. L’image invite à vérifier : LUMO n’est pas un expert qui sait déjà ; c’est un guide patient qui lit, compare et dit ce qui reste inconnu.

Le message pédagogique est de lire la source propre à l’étude pour prédire ce qu’une exécution pourrait changer avant de la lancer, puis de distinguer les faits confirmés des hypothèses et des inconnues. Une illustration n’établit jamais le comportement d’une commande.

## Personnages et cohérence

- **LUMO, stade 3 :** même visage et proportions adultes que les planches officielles, cheveux bouclés auburn, bandeau à motifs, lunettes de laiton relevées, tunique/chemise crème, cape marine au petit nuage blanc, broche-compas, besace en cuir, pantalon brun et bottes lacées. Équipement visible : carte presque vierge, petit compas, exactement deux épingles de route et un petit livre ou rouleau de lecture. Pas de tablier, de trousse à outils, de carnet de repérage ni de lanterne pleine taille. Toute lanterne reste un objet ordinaire en laiton. LUMO observe et vérifie, sans posture d’expert omniscient.
- **Ilyan :** bibliothécaire du code, fidèle à sa planche, avec parchemin portant uniquement des marques abstraites non lisibles.
- **Jo :** responsable du déploiement Kolla-Ansible, fidèle à sa planche et à sa caisse de service standardisée.
- **Maë :** gardienne du registre d’identité, fidèle à sa planche et à son jeton lisse en laiton ; disponible si une scène d’identité est ajoutée plus tard.
- **Noor :** responsable de l’inventaire, fidèle à sa planche, toujours en fauteuil roulant et avec son cadre d’inventaire en laiton.

Tous les personnages sont adultes. Les planches validées sont les références de ressemblance et doivent être jointes lors de la génération.

## Plan des scènes

| ID / fichier | Lieu et personnages | Message pédagogique | Là où l’image s’arrête | Section / emplacement |
|---|---|---|---|---|
| `S3-01-opening` / `S3-01-opening.webp` (1536x1024) | Atelier-bibliothèque du port, établi de lecture en plein jour. LUMO et Ilyan, bibliothécaire du code. | Lire la source permet de formuler ce qu'une opération pourrait changer avant de l'exécuter et de séparer les faits des inconnues. | La scène invite à lire et vérifier ; elle ne montre ni code exécutable, ni commande, ni effet réel d’une opération, ni conclusion technique. | Accueil du module Operate — ouverture, sous le bandeau existant |
| `S3-02-lumo-pose` / `S3-02-lumo-pose.webp` (800x800) | Pose individuelle détourée, fond transparent. LUMO seul, au stade 3 officiel. | LUMO accompagne l’étude avec curiosité et vérifie les éléments avant de conclure. | La pose identifie le guide et l’équipement de l’étape ; elle ne représente pas une expertise absolue ni une opération particulière. | Accueil du module Operate — repère du guide et encadrés pédagogiques |
| `S3-03-rayonnages-etudes` / `S3-03-rayonnages-etudes.webp` (1536x1024) | Archives de l’atelier-bibliothèque, rayonnages en plein jour. Ilyan présente les rayonnages ; LUMO observe avec son petit livre. | Trois études sont publiées pour Ussuri, 2023.1 et 2024.1 ; d’autres sont prévues sans date annoncée. | Les rayonnages pleins et vides distinguent études disponibles et emplacements préparés ; aucune date, version ni échéance n’est lisible ou déduite de l’image. | Start — page d’index des études et choix d’une étude publiée |
| `S3-04-start` / `S3-04-start.webp` (1536x1024) | Établi de lecture et étagère de repérage. LUMO et Ilyan. | Les repères de départ, les conventions et les pages d’orientation aident à trouver rapidement la bonne étude. | L’organisation suggère une orientation claire ; elle ne reproduit pas le menu, les conventions, le nombre de pages ni les instructions réelles du site. | Chaque étude — Start — introduction, trouver vite et conventions |
| `S3-05-operations-predire` / `S3-05-operations-predire.webp` (1536x1024) | Établi de lecture de l’atelier-bibliothèque. LUMO et Jo, responsable du déploiement Kolla-Ansible. | Avant d’exécuter, prédire à partir du code les tâches et les changements attendus, puis comparer cette prédiction aux éléments disponibles. | La comparaison illustre une étape de raisonnement préalable ; elle ne confirme ni les tâches exactes, ni les changements, ni le résultat d’une commande réelle. | Operations — page « Predict an execution » |
| `S3-06-troubleshooting-inconnu` / `S3-06-troubleshooting-inconnu.webp` (1536x1024) | Table de lecture de cartes, dans l’atelier-bibliothèque calme. LUMO et Ilyan. | Dire clairement ce qui reste inconnu fait partie du diagnostic et évite de présenter une hypothèse comme un fait. | La zone blanche représente une limite de connaissance déclarée ; elle n’identifie pas un bug précis, un risque réel ni une solution. | Troubleshooting — bugs connus, questions ouvertes et ce qui n’est pas connu |
| `S3-07-components` / `S3-07-components.webp` (1536x1024) | Deux établis voisins dans l’atelier-bibliothèque. LUMO, Ilyan et Noor en fauteuil roulant avec son cadre d’inventaire. | Les études décrivent séparément les services OpenStack et les composants d’infrastructure qui les soutiennent ainsi que leurs relations documentées. | Les objets évoquent des familles de composants sans attribuer de forme exacte à Keystone, Nova, Neutron, MariaDB, RabbitMQ ou à tout autre service. | Components — pages des services OpenStack et de l’infrastructure de soutien |
| `S3-08-risk-impact` / `S3-08-risk-impact.webp` (1536x1024) | Établi de mécanique et de lecture. LUMO observe ; Jo reste près de sa caisse de service. | Un changement limité peut avoir une portée opérationnelle plus large ; il faut évaluer l’impact et les conditions avant l’action. | La clé et le mécanisme signalent un écart possible entre taille du changement et portée ; ils ne quantifient pas un risque ni ne prédisent un impact réel. | Risk and impact — registre des risques et « un petit changement, une grande charge » |
| `S3-09-concepts-reference` / `S3-09-concepts-reference.webp` (1536x1024) | Coin concepts et référence de l’atelier-bibliothèque. LUMO et Ilyan. | Les pages Concepts expliquent les modèles et les pages Reference rassemblent les constats et termes utiles pour les retrouver. | Les objets distinguent explication conceptuelle et référence consultable ; ils ne représentent pas le dépôt réel, le flot exact d’un déploiement, ni un glossaire ou inventaire littéral. | Concepts — architecture, déroulement, montée en charge et images Kolla ; Reference — constats, glossaire et inventaire |

## Règles communes de production

- Huit scènes en paysage `1536×1024` ; pose détourée de LUMO `800×800`, fond transparent. Aucun bandeau : ceux du parcours existent déjà.
- Style anime-fantasy peint à la main, île méditerranéenne lumineuse, mer turquoise, ciel bleu et grands nuages blancs, pierre blanche, toits de terre cuite, bois, laiton, parchemin et vignes. Plein jour et ombres douces.
- Aucun texte, lettre, chiffre, code lisible ou pseudo-code, commande, version, étiquette, logo, marque ou filigrane. Le petit nuage blanc simple sur la cape de LUMO reste le seul motif de nuage autorisé.
- Garder visages, mains, livre, compas, épingles et objets signatures à l’intérieur d’une marge confortable. Rien d’important ne doit être coupé.
- Les trois études publiées sont évoquées par trois rayonnages garnis aux teintes de bois différentes, sans inscriptions ; des rayonnages vides figurent les études préparées sans date. Ne pas peindre « Ussuri », « 2023.1 » ou « 2024.1 ».
- Les inconnues sont représentées par un espace blanc calme ; le mécanisme de la scène Risk and impact reste intact. Aucune panne n’est une menace.
- Les objets restent génériques : ils ne tiennent pas lieu de preuve pour une commande, un service précis, une topologie ou un résultat d’exécution.

Le manifeste `manifest-stop-3.json` contient les neuf entrées complètes, les prompts anglais commençant par un même bloc de style, les exclusions, les alt en français et les chemins de destination.
