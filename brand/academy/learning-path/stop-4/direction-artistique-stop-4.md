# Direction artistique — Étape 4 « Intervene — VM runbooks »

**Statut :** plan et prompts prêts ; aucune image n’est générée dans ce lot. Les neuf images sont au statut `prompt-only`.

## Intention

Le Stop 4 est le poste de veille sur le pont, au-dessus d’une mer calme, dans la lumière de l’après-midi. L’accent vert `#2C7A43` apparaît dans la végétation, de petits détails de tissu et quelques objets ; il ne code jamais le niveau de risque. Les images accompagnent des runbooks guidés par symptôme pour les VM et les hyperviseurs.

Le principe narratif est : observer sans toucher, comprendre le symptôme et ses causes possibles, agir seulement si les éléments le justifient, vérifier, puis savoir s’arrêter. Les différences entre lecture seule, changement d’état et action destructive se lisent par la forme et la position — carnet ouvert, lanterne fermée qui éclaire, main retenue près d’un outil — et jamais par une couleur seule. Les niveaux de risque sont indiqués dans le site en texte et en icône, pas dans l’image.

## Personnages et cohérence

- **LUMO, stade 4 :** visage et proportions adultes officiels ; cheveux bouclés auburn, bandeau à motifs, lunettes de laiton relevées, chemise crème, cape marine au petit nuage blanc, broche-compas, besace, pantalon brun et bottes lacées. Équipement : carte presque vierge, petit compas, exactement deux épingles, petit livre et carnet de repérage. La lanterne reste petite, ordinaire et en laiton ; pas de tablier, de trousse à outils, de lanterne pleine taille ni de clé de l’étape 6. L’expression dominante est prudente et concentrée.
- **Ren :** officier·ère de veille du pont, fidèle à la planche, avec carnet d’observation et fanion météo simple.
- **Linh :** spécialiste réseau, fidèle à la planche ; son objet signature est la longue-vue en laiton.
- **Safa :** spécialiste des volumes, fidèle à la planche ; son objet signature est la plaque métallique amovible.

Tous les personnages sont adultes. Les feuilles de modèle validées sont les références à joindre lors de la génération. Aucun personnage n’a l’air paniqué, menaçant ou autoritaire.

## Plan des scènes

| ID / fichier | Lieu et personnages | Message pédagogique | Là où l’image s’arrête | Section / emplacement |
|---|---|---|---|---|
| `S4-01-opening` / `S4-01-opening.webp` (1536x1024) | Poste de veille du pont sur la mer calme, après-midi. LUMO au stade 4 et Ren avec carnet d’observation et fanion météo. | Les runbooks guident du symptôme vers des vérifications en lecture seule, puis vers une action seulement si elle est justifiée. | L’image introduit la méthode d’observation ; elle ne décrit aucun incident réel, niveau de risque, diagnostic ni résultat de réparation. | Accueil du module Intervene — ouverture, sous le bandeau existant |
| `S4-02-lumo-pose` / `S4-02-lumo-pose.webp` (800x800) | Pose individuelle détourée, fond transparent. LUMO seul, au stade 4 officiel. | LUMO rappelle de vérifier les faits et de savoir s’arrêter avant une action incertaine. | La pose identifie le guide et l’équipement de l’étape ; elle ne représente ni une action technique ni un niveau de risque. | Accueil du module Intervene — repère du guide et encadrés pédagogiques |
| `S4-03-observer-avant-agir` / `S4-03-observer-avant-agir.webp` (1536x1024) | Établi de veille dans le poste du pont. LUMO et Ren. | Suivre l’ordre : reconnaître le symptôme, observer en lecture seule, comprendre les causes possibles, agir seulement ensuite, puis vérifier. | La séquence enseigne un ordre de lecture ; elle ne constitue pas une procédure exécutable, ne classe pas les risques et ne garantit pas qu’une action convienne. | Accueil — section « Comment suivre un runbook » |
| `S4-04-lifecycle-scheduling` / `S4-04-lifecycle-scheduling.webp` (1536x1024) | Approche du pont de veille, voie encombrée mais stable. LUMO et Ren. | Un état bloqué ou une absence de placement doit être observé et diagnostiqué avant de modifier une instance ou une allocation. | La file évoque une attente ou une absence de place sans représenter BUILD, Placement, un hôte ou une cause déterminée. | Lifecycle — index des runbooks ; Scheduling — index des runbooks |
| `S4-05-migration` / `S4-05-migration.webp` (1536x1024) | Pont stable entre deux rives de l’île. LUMO et Ren observent le passage. | Une migration ou une évacuation s’évalue selon son contexte, sa progression et ses limites ; l’image n’en garantit pas l’issue. | Le convoi représente un passage contrôlé ; il ne prouve pas qu’une migration à chaud ou une évacuation d’hôte puisse réussir. | Migration — page d’index des runbooks |
| `S4-06-networking` / `S4-06-networking.webp` (1536x1024) | Belvédère du pont au-dessus des quais et des canaux de l’île. LUMO et Linh avec longue-vue en laiton. | Observer les chemins, interfaces et passerelles séparément aide à localiser où un symptôme réseau se manifeste. | Les chemins illustrent des frontières à examiner ; ils ne correspondent pas à des interfaces, MTU, règles ou routes précises et ne diagnostiquent pas la connectivité. | Networking — page d’index des runbooks |
| `S4-07-volumes` / `S4-07-volumes.webp` (1536x1024) | Entrepôt calme au pied du pont, avec rangées de caisses standardisées. LUMO et Safa avec plaque métallique amovible. | Un volume bloqué, détaché ou étendu doit être vérifié côté plateforme et côté invité avant toute modification. | Les caisses distinguent présence et retrait ; elles ne montrent pas un état réel d’attachement, de suppression ou d’extension d’un volume. | Volumes — page d’index des runbooks |
| `S4-08-diagnostics-logs` / `S4-08-diagnostics-logs.webp` (1536x1024) | Passerelle d’observation entre tours de l’île. LUMO et Ren, carnets en main. | Suivre un identifiant de requête et lire les journaux par service aide à reconstruire un parcours sans remplacer la vérification des horodatages et des hôtes. | Le parcours visuel évoque un suivi entre services ; il ne reproduit ni les journaux réels, ni un identifiant de requête, ni le chemin précis d’une création de VM. | Diagnostics — index ; Logs — index des journaux et suivi d’une requête |
| `S4-09-recovery` / `S4-09-recovery.webp` (1536x1024) | Poste de veille et pont après une brume légère. Ren et LUMO, calmes et concentrés. | Après un incident, confirmer l’état des services, restaurer prudemment les conditions nécessaires et rouvrir le provisionnement par étapes. | La brume qui se lève suggère une reprise progressive ; elle ne garantit pas la restauration du quorum, d’une API ou du provisionnement. | Recovery — page d’index des runbooks |

## Règles communes

- Huit scènes en paysage `1536×1024` ; pose détourée de LUMO `800×800`, fond transparent. Aucun nouveau bandeau.
- Style peint anime-fantasy d’OzarLand : île méditerranéenne, mer turquoise, ciel bleu et grands nuages blancs, pierre blanche, toits terre cuite, bois, laiton, parchemin et vignes. Après-midi clair, lumière pratique et ombres douces.
- Zéro texte, chiffre, pseudo-écriture, commande, interface lisible, identifiant, étiquette, logo ou filigrane dans les images. Pas de symbole de risque ni d’icône de validation peints.
- Observer et agir se distinguent par gestes, objets et composition, jamais par le seul choix de couleur. Toute lanterne reste un objet ordinaire, petit et non magique.
- Les pannes restent calmes : aucun effondrement, feu, explosion, menace ou urgence dramatisée. Les sujets, mains et objets signatures gardent une marge confortable par rapport aux bords.
- Les objets et scènes sont des métaphores pédagogiques. Ils n’établissent pas un diagnostic ni la sécurité d’une action ; les conditions, pertes possibles et limites sont décrites dans chaque runbook.

Le manifeste `manifest-stop-4.json` contient les neuf entrées complètes, leurs alt en français, leurs emplacements, leurs limites éditoriales, les prompts en anglais commençant par le même bloc de style, les exclusions et les cibles d’intégration.
