# Direction artistique — Étape 1 « Discover — Quick lab »

## Portée et décisions intégrées

Ce document spécifie la production complète des illustrations de l’étape 1 avant toute ouverture des étapes suivantes. Les décisions de parcours sont appliquées : les sept étapes restent un sentier sur la même île ; Alma, Sorel, Ilyan, Ren, Davi et Kest sont les guides de lieu retenus ; les images supplémentaires seront choisies étape par étape ; la carte d’île demeure d’abord une référence de conception ; la production commence et se termine par l’étape 1. Les bandeaux 1600 × 400 existent déjà : aucun nouveau bandeau n’est prévu.

Linh conserve son identité de gardienne du réseau ; son objet signature de référence est la longue-vue en laiton, pas un connecteur. Les planches validées de LUMO et des personnages sont des références officielles, elles ne sont pas régénérées.

## But pédagogique du module

Des scripts construisent en environ une heure un OpenStack 2026.1 complet et jetable sur des VM cloud. Les personnes apprennent en cassant puis réparant le lab, avec une commande de suppression complète. Le message central est : **on peut tout casser, tout réparer et tout effacer ; rien n’est permanent si l’on détruit le lab à la fin.** La page doit dire explicitement « Delete everything when you are done ». Un lab oublié continue de coûter chaque jour : inviter à créer une alerte de budget, sans peindre de prix ni de symbole monétaire.

### Variantes et couverture des exercices

| Lab | Usage décrit dans les pages | Exercices couverts |
|---|---|---|
| Une VM | DHCP, métadonnées, Nova, Open vSwitch, groupes de sécurité et IP flottantes | 01–06 |
| Multinode à 3 VM | Migration à chaud, calcul en panne et maintenance d’hôte | 07–09 |
| Multinode à 5 VM | Perte d’un contrôleur, Galera, RabbitMQ et bascule de VIP | 10–11 ; l’exercice 11 explore la perte de deux contrôleurs et le quorum |

Les 11 exercices restent expliqués par le texte de la page : 01 agents DHCP arrêtés ; 02 agents de métadonnées arrêtés ; 03 nova-compute arrêté ; 04 redémarrer nova-libvirt ; 05 redémarrer l’agent OVS ; 06 instance injoignable de l’extérieur ; 07 calcul en panne, isoler avant d’évacuer ; 08 vider un calcul pour maintenance ; 09 migration à chaud ; 10 perdre un contrôleur ; 11 perdre deux contrôleurs et vérifier le quorum. Aucun libellé, commande, nombre ou détail de service ne doit être peint dans les illustrations.

## Règles de continuité visuelle

- **LUMO, stade 1 :** même visage et proportions adultes, cheveux auburn bouclés, lunettes et bandeau à motifs, chemise crème, cape marine au petit nuage blanc et broche-compas en laiton, besace en cuir, pantalon brun, bottes lacées ; carte presque vierge et petit compas ; aucun tablier ni trousse à outils. La lanterne reste petite, ordinaire et en laiton.
- **Alma :** guide adulte du port, silhouette, tenue et objet signature conformes à la planche validée. Elle accompagne, sans prendre la place de LUMO.
- **Neri, s’il apparaît ultérieurement :** toujours l’homme adulte aux cheveux bruns bouclés, barbe courte, foulard marine, chemise crème, gilet et pantalon bruns, sac à dos et sac de couchage roulé.
- Style anime-fantasy peint à la main comme les références : ciel bleu lumineux, nuages blancs, mer turquoise, pierre blanche, toits terracotta, bois, laiton, parchemin, vigne, fanions marine au nuage blanc simple. Lumière chaude, ombres douces, scènes accueillantes et lisibles. Accent de l’étape : mer **#1E9FB5**.
- Aucun texte, lettre, chiffre, logo, pseudo-écriture, filigrane, symbole monétaire ou marque produit dans l’image. Pas de catastrophe : les pannes se lisent par une brume calme, une houle légère ou une lanterne qui vacille.
- Aucun bandeau neuf ; cadrer les scènes pour une illustration de page, et non pour un recadrage en bandeau. Ne jamais mettre un détail pédagogique indispensable dans les coins.
- Le site porte les commandes, le coût, la version 2026.1, les noms des services et les avertissements. L’image accompagne la lecture et ne prouve pas un comportement technique.

**Total planifié : 8 images sur un maximum de 10.** Les statuts restent `prompt-only` : aucune image n’est générée dans cette livraison.

## Plan des huit scènes

### 1. `S1-opening.webp` — Accueil — ouverture du module (illustration d’accueil, sans nouveau bandeau)

- **Format :** 1536x1024 WebP.
- **Lieu et personnages :** Port au matin, portail de pierre blanche et ponton temporaire ; LUMO au stade 1 et Alma.
- **Message pédagogique :** Le Quick lab est un environnement temporaire que l’on prépare pour apprendre, puis que l’on détruit à la fin.
- **Là où l’image s’arrête :** L’image présente un lieu d’apprentissage accueillant ; elle ne montre ni les scripts, ni un schéma de VM, ni une garantie de durée ou de résultat.

### 2. `S1-lumo-pose.webp` — Accueil — encadré d’introduction et repère de progression

- **Format :** 800x800 WebP.
- **Lieu et personnages :** LUMO seul en pied, sur fond transparent, avec la carte et le petit compas du stade 1.
- **Message pédagogique :** Commencer par comprendre l’environnement et les consignes avant de lancer un exercice jetable.
- **Là où l’image s’arrête :** La pose rappelle l’équipement validé de LUMO ; elle ne tient pas lieu de procédure ni de commande.

### 3. `S1-03-choisir-son-lab.webp` — Accueil — section « Choisir son lab »

- **Format :** 1400x900 WebP.
- **Lieu et personnages :** Deux appontements contrastés au port ; LUMO et Alma comparent un ponton compact et un ponton multinode.
- **Message pédagogique :** Choisir une VM pour les services de base ou une configuration multinode selon les exercices que l’on veut pratiquer.
- **Là où l’image s’arrête :** L’image distingue deux familles de choix, sans annoncer le nombre de VM, les services disponibles, les prérequis ou la topologie exacte.

### 4. `S1-04-cycle-creer-utiliser-detruire.webp` — Accueil — section « Créer, utiliser, détruire » et rappel de fin de session

- **Format :** 1400x900 WebP.
- **Lieu et personnages :** Un seul ponton est montré avant, pendant et après l’usage ; LUMO désigne le quai rendu vide.
- **Message pédagogique :** Créer le lab, l’utiliser pour apprendre, puis tout supprimer lorsque l’on a terminé.
- **Là où l’image s’arrête :** La séquence ne représente pas les commandes réelles ni la suppression de ressources au niveau technique. Le rappel de coût et l’alerte budgétaire sont écrits dans la page, sans montant ni symbole monétaire dans l’image.

### 5. `S1-05-reseau-et-agents.webp` — Accueil — aperçu des exercices 01, 02, 05 et 06 ; pages de ces exercices

- **Format :** 1200x750 WebP.
- **Lieu et personnages :** Chemins portuaires et petits pavillons de service ; quelques adultes suivent les connexions, une brume légère masque une voie.
- **Message pédagogique :** Vérifier les agents DHCP et de métadonnées ainsi que le chemin OVS avant de conclure qu’une instance est accessible depuis l’extérieur.
- **Là où l’image s’arrête :** Le décor ne décrit pas les réseaux réels de Neutron, les agents ou le dataplane et ne permet pas d’identifier seul la cause d’une perte d’accès.

### 6. `S1-06-calcul-et-libvirt.webp` — Accueil — aperçu des exercices 03, 04 et 09 ; pages des exercices nova-compute, libvirt et migration

- **Format :** 1200x750 WebP.
- **Lieu et personnages :** Atelier calme avec deux structures de rack ; un opérateur inspecte un mécanisme et un autre accompagne un chariot entre deux établis.
- **Message pédagogique :** Distinguer l’arrêt de nova-compute, le redémarrage de nova-libvirt et le déplacement contrôlé d’une instance.
- **Là où l’image s’arrête :** L’image ne décrit pas les conditions d’une migration à chaud et ne prétend pas qu’un redémarrage ou un déplacement est toujours sans interruption.

### 7. `S1-07-panne-et-maintenance.webp` — Accueil — aperçu des exercices 07 et 08 ; pages panne de calcul et maintenance d’hôte

- **Format :** 1200x750 WebP.
- **Lieu et personnages :** Quai de service ; un rack est mis à l’écart, un second est préparé pour maintenance par des adultes méthodiques.
- **Message pédagogique :** Isoler et comprendre le calcul en panne avant d’évacuer des instances, puis vider un hôte avant sa maintenance planifiée.
- **Là où l’image s’arrête :** La scène ne prescrit pas une évacuation, ne détermine pas si un hôte est sûr et n’explique pas la procédure de maintenance.

### 8. `S1-08-controleurs-et-quorum.webp` — Accueil — aperçu des exercices 10 et 11 ; pages perte d’un contrôleur et perte de deux contrôleurs

- **Format :** 1200x750 WebP.
- **Lieu et personnages :** Trois tours de contrôle reliées au-dessus d’un port calme ; deux lanternes s’assombrissent dans une brume légère, des opérateurs observent.
- **Message pédagogique :** Distinguer la perte d’un contrôleur de la perte de quorum quand deux contrôleurs sont indisponibles.
- **Là où l’image s’arrête :** La métaphore ne définit ni le quorum réel, ni le comportement de Galera, RabbitMQ ou d’une VIP ; ces faits doivent venir des versions, sources et procédures du lab.

## Critères de livraison

- Les deux fichiers de cette livraison sont le présent plan et `manifest-stop-1.json`.
- Chaque entrée du manifeste comporte un prompt anglais complet, qui commence par le bloc commun de style, un négatif réutilisable, un texte alternatif français, `status: "prompt-only"` et le chemin d’intégration sous `overrides/assets/images/ozarland/stop-1/`.
- Les scènes 05 à 08 regroupent les exercices par familles ; aucune scène ne remplace les 11 explications et procédures écrites.
- Le cycle de vie inclut visuellement le quai entièrement vidé ; le texte de la page garde le rappel explicite de suppression et l’avertissement de coût.
