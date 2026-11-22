# Direction artistique — Stop 2 « Deploy — Deployment patterns »

**Statut :** plan validé pour production ; les neuf images restent `prompt-only`. Ce dossier ne contient ni image générée ni bandeau. Les prompts de `manifest-stop-2.json` sont autonomes et commencent tous par le bloc de style commun.

## Intention

L’atelier des modèles se trouve au bord du port, dans une lumière claire du matin. Le bois, le laiton, la pierre blanche, le ciel bleu (#2F6FD0) et la mer turquoise prolongent l’identité d’OzarLand. Sorel, Jo et LUMO invitent à comparer les patterns avec sérieux et curiosité, sans imposer une architecture. Les modèles peints restent des métaphores d’orientation : les pages contiennent les critères, les versions, les commandes et les sources.

**Principe de composition des comparaisons :** les options côte à côte ont la même taille pertinente, le même soin, le même éclairage et la même dignité. Aucun code vert/rouge, coche, podium, prix, couronne, mise en avant ou gagnant visuel. Une différence de forme sert seulement à distinguer les objets.

## Continuité des personnages

- **LUMO — stade 2 :** le même jeune adulte androgyne des planches officielles ; visage et proportions inchangés, cheveux auburn bouclés, bandeau à motifs, lunettes de protection relevées, chemise crème, cape marine au petit nuage blanc et broche-compas en laiton, besace de cuir, pantalon brun et bottes lacées. LUMO garde la lanterne ordinaire en laiton. À ce stade, montrer la carte presque vierge, le petit compas et deux épingles de route. Aucun tablier ni trousse d’outils du stade 0, aucun livre du stade 3, aucun carnet du stade 4.
- **Sorel :** reprendre la silhouette, le visage et la tenue de la planche officielle ; maître·sse adulte des maquettes, avec deux maquettes vierges comme objet signature.
- **Jo :** reprendre la silhouette, le visage et la tenue de la planche officielle ; responsable adulte du déploiement Kolla-Ansible, avec une caisse de service standardisée.
- Les autres figurants éventuels sont des adultes divers, aux tenues pratiques ; aucune profession n’est assignée à un genre ou une origine.

## Plan des scènes

| Image | Lieu et personnages | Message pédagogique | Là où l’image s’arrête | Section/page |
|---|---|---|---|---|
| `S2-01-opening.webp` | Atelier de modèles au bord du port ; matin lumineux ; Sorel, Jo et LUMO ; deux routes-maquettes vierges. | Les patterns se comparent par contexte, bénéfices et limites. | N’illustre aucune topologie, commande ou recommandation réelle. | Accueil — ouverture du module. |
| `S2-02-lumo-pose.webp` | LUMO en pied, fond transparent ; stade 2. | Le guide accompagne une comparaison ouverte. | N’est ni un pattern ni un conseil de déploiement. | Accueil — guide et introduction. |
| `S2-03-topologies.webp` | Deux maquettes côte à côte, compacte et multinœud ; Sorel, Jo, LUMO. | Les formes de déploiement répondent à des contextes différents. | Les configurations exactes et prérequis appartiennent à la page. | Topologies — index. |
| `S2-04-networking-storage.webp` | Établis de chemins de réseau et de supports de stockage ; LUMO et collègues adultes. | Réseau et stockage offrent plusieurs choix à comparer selon les besoins. | Ne nomme ni ne prouve les technologies ou backends. | Networking — index ; Storage — index. |
| `S2-05-configuration-secrets.webp` | Établi de configuration rangé avec un coffret fermé et scellé ; LUMO et une collègue adulte. | Les choix de configuration et la protection des secrets exigent une attention distincte. | Aucun fichier, contenu secret, certificat ou valeur n’est montré. | Configuration — index. |
| `S2-06-services.webp` | Halle ouverte sur le port avec stations de services non marquées ; LUMO et opérateurs adultes. | Les services s’intègrent dans un contexte et demandent des vérifications propres. | Les formes n’identifient pas les produits et ne garantissent pas la disponibilité. | Services — index. |
| `S2-07-deployment-errors.webp` | Une pièce de maquette décalée, brume légère ; LUMO prudent et Jo attentif. | Diagnostiquer méthodiquement des erreurs variées. | Pas de panne précise, catastrophe ou réparation automatique. | Deployment errors — index. |
| `S2-08-operations-version-notes.webp` | Petite zone de maintenance ; Jo et LUMO remplacent une pièce, le reste reste intact. | Encadrer les changements et vérifier avant/après, y compris lors d’une mise à niveau. | Ne prescrit aucune commande, procédure de sauvegarde ou garantie de retour arrière. | Operations — index ; Version notes — index. |
| `S2-09-comparisons.webp` | Deux maquettes d’égale importance sur une même table ; Sorel, Jo et LUMO. | Des patterns opposés peuvent chacun convenir à leur contexte. | Ne classe aucune technologie, architecture ou nombre de contrôleurs. | Comparisons — index. |

## Couverture éditoriale des pages

- **Topologies :** lab tout-en-un sur une VM ; trois contrôleurs et deux calculs imbriqués dans un cloud OpenStack. L’image suggère les échelles ; les quantités et l’imbrication exactes sont expliquées en HTML.
- **Networking :** interfaces, VLAN, MTU, OVS et OVN ; réseaux provider flat ou VLAN.
- **Storage :** backends Cinder et Glance (LVM, Ceph, NFS) ; disques Nova locaux, Ceph RBD ou démarrage sur volume.
- **Configuration :** CPU pinning, hugepages, NUMA, inventaire, globals, overrides, secrets, registre local, mode hors ligne, rotation de passwords.yml sans afficher son contenu, SR-IOV, alias PCI et TLS interne/externe.
- **Services :** journalisation centrale, Designate/Bind9, Ceph externe pour Glance/Cinder/Nova, supervision/alertes, Octavia et certificats/réseau de gestion d’amphora.
- **Deployment errors :** neuf pages, couvrant versions Ansible, HAProxy/VIP interne, bootstrap Fernet, cluster MariaDB arrêté, conflit d’adresse ProxySQL, enregistrement nova-compute, registre non sécurisé, cluster RabbitMQ et mises à jour automatiques affectant MariaDB.
- **Operations :** sept pages, couvrant ajout/retrait/remplacement de calcul, bootstrap-servers, vérification après changement, deploy/reconfigure/upgrade, limitation d’exécution, sauvegarde/restauration MariaDB et remplacement de contrôleur.
- **Version notes :** passage 2025.1→2026.1 et rapport de mise à niveau du lab tout-en-un ; traité par la scène de changement contrôlé de `S2-08`.
- **Comparisons :** Docker/Podman, ML2/OVS/ML2/OVN, nœuds réseau séparés/services réseau sur contrôleurs, un contrôleur/trois contrôleurs. Les deux côtés restent visuellement égaux.

## Production et intégration

- **Neuf images au total :** huit scènes en 1536×1024 et une pose de LUMO en 800×800 avec transparence alpha. Aucun nouveau bandeau : les bandeaux existants restent en place.
- Toutes les images sont au statut `prompt-only`. Les fichiers à générer sont en WebP, avec les noms et chemins du manifeste.
- Joindre les planches officielles de LUMO et des personnages lors de la génération. Vérifier avant livraison : LUMO stade 2 exact ; Sorel et Jo fidèles ; aucun livre/carnet prématuré ; composition centrée et sûre pour un recadrage ; aucune lettre, aucun chiffre, aucune étiquette, commande, marque ou contenu secret.
- Dans les comparaisons, relire l’équilibre à taille réelle et en niveaux de gris : aucun côté ne doit recevoir plus de lumière, d’espace ou de finition.
- Texte, critères, résultats de commande et détails d’architecture restent dans la page accessible, pas dans l’image.
