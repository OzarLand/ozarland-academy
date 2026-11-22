# Direction artistique — Étape 6 « Compare — OKD OpenStack lab »

**Statut :** plan et prompts prêts ; aucune image n’est générée dans ce lot. Les neuf entrées du manifeste sont au statut `prompt-only`.

## Intention

L’étape se déroule dans la citadelle d’automates sur un promontoire côtier, en fin de journée sous une lumière légèrement plus froide et lisible. Le marine `#1F3A6B` est l’accent principal. La peinture conserve l’identité de l’Academy : ciel bleu, mer turquoise, pierre blanche, toits de terre cuite, bois, laiton, parchemin, vignes et petites bannières marine portant un nuage blanc simple.

Le module présente un lab OpenStack exécuté par des opérateurs Kubernetes sur OKD pour des opérateurs qui connaissent Kolla-Ansible. Le message central est une boucle d’observation, de comparaison à l’état voulu et de réconciliation selon des règles, des préconditions et un périmètre. Une modification manuelle peut être annulée par cette boucle. Il faut vérifier versions, préconditions et limites du retour arrière.

Les mécanismes restent des outils : calmes, sans visage, strictement contraints par leurs rails et leurs règles visibles. Ils ne prennent pas de décisions, ne diagnostiquent pas seuls et ne réparent rien sans conditions. La scène de comparaison donne la même taille, lumière, dignité et importance aux deux approches.

## Personnages et cohérence

- **LUMO, stade 6 :** même visage androgyne adulte et mêmes proportions que les planches officielles ; cheveux auburn bouclés, bandeau à motifs, lunettes de protection en laiton relevées, chemise crème, cape marine avec petit nuage blanc simple et broche-compas en laiton, besace en cuir de capacité normale, pantalon brun et bottes lacées. Équipement visible : carte presque vierge, petit compas, exactement deux épingles de route, petit livre de lecture, carnet de repérage, lanterne ordinaire en laiton à taille pleine et petite clé de laiton fixée à la ceinture. La besace n’est pas pleine et la carte n’est pas presque complète. LUMO reste patient·e, curieux·se et honnête sur l’incertitude ; il ou elle observe et vérifie plutôt que de se présenter comme expert·e omniscient·e.
- **Kest :** gardien·ne adulte des mécanismes de la citadelle, exactement selon la planche approuvée, avec son levier de commande manuel.
- **Jo**, lorsque présent·e : responsable adulte du déploiement Kolla-Ansible, exactement selon la planche approuvée, avec sa caisse de service standardisée.
- **Noor**, lorsque présent·e : responsable adulte de l’inventaire, toujours en fauteuil roulant avec son cadre d’inventaire en laiton, exactement selon la planche approuvée.

Les prompts n’inventent pas de nouveaux attributs physiques pour Kest, Jo ou Noor. Toute présence secondaire reste adulte et respecte les références officielles.

## Plan des scènes

| ID / fichier | Lieu / scène | Personnages | Message pédagogique | Là où l’image s’arrête | Section du site |
|---|---|---|---|---|---|
| `S6-01-opening` / `S6-01-opening.webp` (1536x1024) | Entrée de la citadelle de pierre blanche sur le promontoire côtier. | LUMO et Kest. | Présenter un lab OpenStack piloté par des opérateurs Kubernetes comme un système reproductible dont l’état voulu, les préconditions et les limites restent à vérifier. | La scène situe le lab dans la citadelle ; elle ne promet ni comportement automatique sans condition, ni réparation autonome, ni équivalence littérale avec un environnement OKD réel. | Accueil de l’étape 6 — illustration d’ouverture |
| `S6-02-lumo-pose` / `S6-02-lumo-pose.webp` (800x800) | Pose détourée, fond transparent, sans décor. | LUMO. | LUMO accompagne la comparaison en signalant ce qui est observé et ce qui reste à vérifier. | La pose identifie LUMO et l’équipement du stade 6 ; elle ne représente ni une validation technique ni une promesse de résultat. | Accueil et encadrés de l’étape 6 — pose réutilisable du guide |
| `S6-03-comparer` / `S6-03-comparer.webp` (1536x1024) | Atelier de maquettes au bord du port, deux modèles côte à côte. | LUMO, Jo et Kest. | Comparer deux modèles d’exploitation avec un poids visuel égal, en partant du contexte et des responsabilités de chaque approche. | Les deux maquettes illustrent des modèles d’exploitation à comparer ; aucune option n’est universellement meilleure et la scène ne prescrit pas un choix. | Concepts — page d’index, comparaison entre Kolla-Ansible et les opérateurs |
| `S6-04-concepts` / `S6-04-concepts.webp` (1536x1024) | Atelier intérieur de la citadelle, boucle mécanique sur rails fixes. | LUMO et Kest. | Une boucle d’observation, de comparaison et d’action applique des règles et un périmètre déclarés, sous des préconditions à vérifier. | Le mouvement illustre une réconciliation selon un état déclaré ; il ne prouve pas que des opérateurs corrigent tout écart, ni qu’ils agissent sans conditions, délai ou risque. | Concepts — réconciliation et état voulu |
| `S6-05-installation` / `S6-05-installation.webp` (1536x1024) | Maquette de citadelle côtière assemblée par niveaux sur une base stable. | LUMO et Noor. | L’installation se prépare par étapes distinctes, des fondations et services de plateforme jusqu’aux plans OpenStack et à leur vérification. | Les niveaux représentent une séquence d’installation à comprendre ; ils ne constituent ni une procédure exhaustive, ni une topologie de référence, ni une preuve de disponibilité. | Installation — page d’index |
| `S6-06-operations` / `S6-06-operations.webp` (1536x1024) | Salle des opérations de la citadelle. | LUMO et Kest. | Les opérations passent par le contrôle prévu et une vérification du changement, plutôt que par une manipulation manuelle directe des mécanismes. | La scène rappelle l’usage d’un contrôle prévu ; elle ne montre aucune commande réelle, ne garantit pas son effet et ne dispense pas de vérifier versions, préconditions et limites. | Operations — page d’index |
| `S6-07-troubleshooting` / `S6-07-troubleshooting.webp` (1536x1024) | Travée mécanique calme de la citadelle. | LUMO et Kest. | Quand une réconciliation n’avance pas ou annule une modification manuelle, il faut observer les conditions et les dépendances avant d’agir. | La scène évoque un symptôme et une modification manuelle réconciliée ; elle n’identifie pas une cause réelle et n’indique pas une correction universelle. | Troubleshooting — page d’index |
| `S6-08-lifecycle` / `S6-08-lifecycle.webp` (1536x1024) | Établi de maintenance dans la citadelle. | LUMO et Kest. | Une mise à jour ou une restauration demande des préconditions, une pièce de rechange adaptée et une compréhension des limites du retour arrière. | La pièce conservée évoque une préparation au retour arrière ; elle ne garantit pas qu’une mise à jour soit réversible ni qu’une restauration soit complète. | Lifecycle — page d’index |
| `S6-09-knowledge-base` / `S6-09-knowledge-base.webp` (1536x1024) | Salle d’archives intégrée à la citadelle. | LUMO et Noor. | La base de connaissances rassemble des fiches et l’état du lab tout en laissant visibles les questions encore ouvertes. | La salle représente des références, l’état du lab et les questions ouvertes ; elle ne suggère pas que toute connaissance est complète ou que les exemples valent pour chaque environnement. | Knowledge base — page d’index |

## Règles communes

- Huit illustrations de scène en paysage `1536×1024` et une pose détourée de LUMO en `800×800` avec vraie transparence alpha. Aucun bandeau.
- Le bloc de style commun précède chaque prompt. Les prompts utilisent les planches de LUMO au stade 6, expressions et vues, et la planche des personnages comme références visuelles obligatoires.
- Exactement deux épingles de route sur LUMO ; une petite clé de laiton à la ceinture ; lanterne pleine taille ordinaire ; carte presque vierge ; besace de capacité normale. Ne pas montrer la progression de l’étape 7.
- Aucun texte, lettre, chiffre, code, pseudo-écriture, étiquette, inscription, logo, filigrane, écran lisible ou marque de produit. Les panneaux, parchemins, livres, tiroirs et cartes restent vierges ou sans marques lisibles.
- Aucun robot, créature, visage ou personnalité sur les automates. Pas de catastrophe, d’urgence, de magie, de réparation autonome inconditionnelle ou de garantie de fonctionnement.
- Les illustrations sont des métaphores pédagogiques. Elles ne reproduisent pas une architecture réelle, une interface, une commande, un état garanti ou une procédure d’exploitation.
- Garder les personnages, mains et objets-signatures à distance des bords et conserver une composition lisible sur téléphone.

Le manifeste contient les neuf prompts complets en anglais, chacun précédé du bloc de style commun, avec texte alternatif français, emplacement, message pédagogique, limite éditoriale et chemin cible.
