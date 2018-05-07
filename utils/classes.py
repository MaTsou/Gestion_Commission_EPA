#!/usr/bin/env python3
#-*- coding: utf-8 -*-

# Ce fichier contient les classes utiles dans commission.py :
###
# 1/ Classe Fichier :
#   Contient le contenu (dossiers) d'un fichier dont le nom est
#   passé au constructeur.
#   Réuni toutes les méthodes agissant sur ces dossiers.
# 2/ Classe Client :
#   Classe 'générique', n'est pas utilisée en tant que telle mais
#   sert de classe mère aux classes Jury et Admin. Elle est le
#   prototype des objets qui se connectent au serveur.
# 3/ Classe Jury :
#   Client de type 'jury' de commission.
# 4/ Classe Admin :
#   Client de type 'administrateur' de commission.
###

import os, sys, glob, pickle
from parse import parse
from lxml import etree
import utils.interface_xml as xml
import utils.boite_a_outils as outil
from utils.parametres import filieres
from utils.parametres import nb_jurys

#################################################################################
#                               Fichier                                         #
#################################################################################
class Fichier(object):
    """ objet fichier : son but est de contenir toutes les méthodes qui agissent
    sur le contenu des fichiers, i.e. les dossiers de candidatures. Ces fichiers
    sont des attributs des objets 'Client' que gère l'objet 'Serveur'."""

    # Attributs de classe
    _criteres_tri = {
            'score_b' : lambda cand: -float(xml.get(cand, 'Score brut').replace(',','.')),
            'score_f' : lambda cand: -float(xml.get(cand, 'Score final num').replace(',','.')),
            'alpha' : lambda cand: xml.get(cand, 'Nom')
            }

    def __init__(self, nom):
        # stockage du nom
        self.nom = nom
        # A priori, il n'est pas nécessaire de vérifier que le
        # fichier 'nom' existe, cela a été fait avant la construction
        parser = etree.XMLParser(remove_blank_text=True) # pour que pretty_print fonctionne
        self._dossiers = etree.parse(nom, parser).getroot()
        # On créé aussi l'ensemble (set) des identifiants des candidats
        self._identif = {xml.get(cand, 'Num ParcoursSup') for cand in self._dossiers}
        # On récupère la filière. Utilisation d'un set pour éviter les doublons !
        self._filiere = {fil for fil in filieres if fil in nom.lower()}.pop()

    def __iter__(self):
        # Cette méthode fait d'un objet fichier un itérable (utilisable dans une boucle)
        # Cela sert à créer la liste de dossiers qui apparaît dans la page html de traitement
        # On itère sur la liste de dossiers que contient le fichier.
        return self._dossiers.__iter__()

    def __contains__(self, cand):
        # méthode qui implémente l'opérateur 'in'.
        # la syntaxe est 'if cand in objet_Fichier'
        # dans laquelle cand est un noeud xml pointant sur un candidat.
        # Elle retourne un booléen. Utile pour l'admin qui traite un
        # candidat et reporte dans toutes les filières demandées.
        return xml.get(cand, 'Num ParcoursSup') in self._identif
    
    def __len__(self):
        # Cette méthode confère un sens à l'opération len(fichier)
        return len(self._dossiers)

    def cand(self, index):
        # Renvoie le noeud candidat indexé par 'index' dans self._dossiers
        return self._dossiers[index]

    def get_cand(self, cand):
        # Renvoie le candidat dont l'identifiant est identique à celui de cand
        # Ne sert qu'à l'admin quand il traite un candidat sur une filière
        # et REPORTE ses modifs dans toutes les filières demandées..
        # Sert aussi à la fonction stat() dans la toolbox.
        # À n'utiliser que sur des fichiers contenant le candidat ('cand in fichier' True)
        index = 0
        while xml.get(cand, 'Num ParcoursSup') != xml.get(self._dossiers[index], 'Num ParcoursSup'):
            index += 1
        return self._dossiers[index]

    def filiere(self):
        # renvoie la filière
        return self._filiere

    def convert(self, naiss):
        # Convertit une date de naissance en un nombre pour le classement
        dic = parse('{j:d}/{m:d}/{a:d}', naiss)
        return dic['a']*10**4 + dic['m']*10**2 + dic['j']

    def ordonne(self, critere):
        # renvoie une liste des candidatures ordonnées selon le critère demandé
        # (critère appartenant à l'attribut de classe _critere_tri)
        # Classement par age
        doss = sorted(self._dossiers, key = lambda cand: self.convert(cand.xpath('naissance')[0].text))
        # puis par critere
        return sorted(doss, key = Fichier._criteres_tri[critere])

    def sauvegarde(self):
        # Sauvegarde le fichier : mise à jour (par écrasement)
        # du fichier xml
        with open(self.nom, 'wb') as fich:
            fich.write(etree.tostring(self._dossiers, pretty_print=True, encoding='utf-8'))

#################################################################################
#                               Class Client                                    #
#################################################################################

class Client(): 
    """ Objet client "abstrait" pour la class Serveur"""
    def __init__(self, key, droits):
        # constructeur
        # identifiant du client : contenu du cookie déposé sur la machine client
        self.je_suis = key  
        self._droits = droits  # droits : admin ou jury... Attribut privé car méthode set particulière..
        self.fichier = None  # contiendra une instance 'Fichier'
        # Index (dans le fichier) du candidat suivi.
        self.num_doss = -1  # -1 signifie : le jury n'est pas en cours de traitement
    
    def get_droits(self):
        return self._droits

    def get_cand(self) : # renvoie le candidat courant
        return self.fichier.cand(self.num_doss)
        
    def set_fichier(self, fich):
        self.fichier = fich
        r = parse('{}_{}.xml', fich.nom) # récupère nom de la filière traitée
        self._droits += ' {}'.format(r[1])
        self.num_doss = 0 # on commence par le premier !

#################################################################################
#                               Class Jury                                      #
#################################################################################

class Jury(Client): 
    """  Objet client (de type jury de commission) pour la class Serveur"""
    def __init__(self, key):
        # constructeur : on créé une instance Client avec droits "jury" 
        Client.__init__(self, key, 'Jury')
        # Fichiers javascripts
        self.script_menu = 'utils/scripts/menu_jury.js'
        self.script_dossiers = 'utils/scripts/dossiers_jury.js'

    # Accesseurs et mutateurs
    def set_droits(self, droits):
        self._droits = 'Jury' + droits

    # Estimation du rg final d'un candidat
    def get_rgfinal(self, cand):
        # On récupère les dossiers traités seulement
        doss = [ca for ca in self.fichier if (xml.get(ca, 'traité') != '' and xml.get(ca, 'Correction') != 'NC')]
        # Ceux-ci sont classés par ordre de score final décroissant
        doss[:] = sorted(doss, key = lambda cand: -float(xml.get(cand, 'Score final num').replace(',','.')))
        # On calcule le rang du score_final actuel (celui de cand) dans cette liste
        rg = outil.rang(cand, doss, 'Score final num')
        # À ce stade, rg est le rang dans la liste du jury. 
        # La suite consiste à calculer n*(rg-1) + k
        # où n est le nombre de jurys et k l'indice du jury courant.
        q = parse('Jury {:w}{:d}', self._droits)
        n = int(nb_jurys[q[0].lower()])
        k = int(q[1])
        return n*(rg-1)+k

    def traiter(self, **kwargs):
        # Fonction lancée par la fonction "traiter" du Serveur. Elle même est lancée par validation d'un dossier
        # On récupère le candidat
        cand  = self.get_cand()
        ## On met à jour le contenu de ce dossier :
        # 1/ correction apportée par le jury et score final
        if kwargs['nc'] == 'NC':
            cor, scoref = 'NC', 'NC'
        else:
            cor = kwargs['correc']
            note = float(xml.get(cand, 'Score brut').replace(',','.')) + float(cor)
            scoref = '{:.2f}'.format(note).replace('.',',')
        xml.set(cand, 'Correction', cor)
        xml.set(cand, 'Score final', scoref)
        # 2/ Qui a traité le dossier
        xml.set(cand, 'Jury', self._droits)
        # 2bis/ On met à jour le fichier des décomptes de commission
        if (not(xml.get(cand, 'traité')) and cor != 'NC'): # seulement si le candidat n'a pas déjà été vu et si classé!
            with open(os.path.join(os.curdir,"data","decomptes"), 'br') as fich:
                decompt = pickle.load(fich)
            qui = self._droits
            for key in decompt.keys():
                if key in qui:
                    decompt[key] += 1
            with open(os.path.join(os.curdir, "data", "decomptes"), 'wb') as stat_fich:
                pickle.dump(decompt, stat_fich)
        # 3/ "bouléen" traite : le dossier a été traité (classé ou non classé)
        xml.set(cand, 'traité', 'oui')
        print('traité ok')
        # 4/ motivation du jury
        xml.set(cand, 'Motifs', kwargs['motif'])
        print('Motifs ok')
        ## Fin mise à jour dossier
        # On sélectionne le dossier suivant
        if self.num_doss < len(self.fichier)-1:
            self.num_doss += 1
        # Et on sauvegarde le tout
        self.fichier.sauvegarde()

#################################################################################
#                               Class Admin                                     #
#################################################################################
class Admin(Client): 
    """ Objet client (de type Administrateur) pour la class Serveur"""
    def __init__(self, key): 
        # constructeur : on créé une instance Client avec droits "admin"
        Client.__init__(self, key, 'Administrateur')
        # Fichiers javascripts
        self.script_menu = 'utils/scripts/menu_admin.js'
        self.script_dossiers = 'utils/scripts/dossiers_admin.js'
    
    def set_droits(self, droits):
        self._droits = 'Administrateur' + droits

    def traiter(self, **kwargs):
        # Traitement dossier avec droits administrateur
        # On récupère le candidat courant
        cand = self.get_cand()
        # Ici, on va répercuter les complétions de l'administrateur dans tous les dossiers que le
        # candidat a déposé.
        # Attention ! le traitement du fichier en cours est fait à part car deux objets 'Fichier' qui
        # auraient le même nom sont malgré tout différents !! On rajoute le bon fichier juste après.
        # Recherche de tous les fichiers existants :
        list_fich_admin = [Fichier(fich) for fich in glob.glob(os.path.join(os.curdir, "data", "admin_*.xml"))\
                if fich != self.fichier.nom]
        # On restreint la liste aux fichiers contenant le candidat en cours
        list_fich_cand = [fich for fich in list_fich_admin if cand in fich]
        # On rajoute le fichier suivi actuellement
        list_fich_cand.append(self.fichier)
        ############### Admin a-t-il changé qqc ? Si oui, mise à jour. 
        # Classe actuelle ?
        if xml.get(cand, 'Classe actuelle') != kwargs['Classe actuelle']:
            for fich in list_fich_cand: xml.set(fich.get_cand(cand), 'Classe actuelle', kwargs['Classe actuelle'])
            # semestres ?
        txt = kwargs.get('sem_prem','off')  # kwargs ne contient 'sem_prem' que si la case est cochée !
        for fich in list_fich_cand: xml.set(fich.get_cand(cand), 'sem_prem', txt)
        txt = kwargs.get('sem_term','off')  # kwargs ne contient 'sem_term' que si la case est cochée !
        for fich in list_fich_cand: xml.set(fich.get_cand(cand), 'sem_term', txt)
            # Cas des notes
        matiere = ['Mathématiques', 'Physique/Chimie']
        date = ['trimestre 1', 'trimestre 2', 'trimestre 3']
        classe = ['Première', 'Terminale']
        for cl in classe:
            for mat in matiere:
                for da in date:
                    key_script = '{}{}{}'.format(cl[0], mat[0], da[-1])
                    key = '{} {} {}'.format(mat, cl, da)
                    if xml.get(cand, key) != kwargs[key_script]:
                        for fich in list_fich_cand: xml.set(fich.get_cand(cand), key, kwargs[key_script])
            # CPES
        liste = ['Mathématiques CPES', 'Physique/Chimie CPES', 'Écrit EAF', 'Oral EAF']
        for li in liste:
            if 'cpes' in li.lower():
                if ('cpes' in xml.get(cand, 'Classe actuelle').lower()) and xml.get(cand, li) != kwargs[li]:
                    for fich in list_fich_cand: xml.set(fich.get_cand(cand), li, kwargs[li])
            else:
                if xml.get(cand, li) != kwargs[li]:
                    for fich in list_fich_cand: xml.set(fich.get_cand(cand), li, kwargs[li])
        # On (re)calcule le score brut !
        outil.calcul_scoreb(cand)
        # Commentaire éventuel admin + gestion des 'NC'
        # Les commentaires admin sont précédés de '- Admin :' c'est à cela qu'on les reconnaît
        # Notamment, script.js exclut qu'un tel commentaires soit considéré comme une motivation
        # de jury.
        motif = kwargs['motif']
        if not('- Admin :' in motif or motif == ''):
            motif = '- Admin : {}'.format(motif)
        if kwargs['nc'] == 'NC':
            # L'admin a validé le formulaire avec le bouton NC (le candidat ne passera pas en commission)
            # Pour ce cas là, on ne recopie pas dans toutes les filières. Admin peut exclure une candidature
            # dans une filière sans l'exclure des autres. Sécurité !
            xml.set(cand, 'Correction', 'NC') # la fonction calcul_scoreb renverra 0 !
            xml.set(cand, 'Jury', 'Admin')
            xml.set(self.fichier.get_cand(cand), 'Motifs', motif)
        else:
            for fich in list_fich_cand:
                xml.set(fich.get_cand(cand), 'Correction', '0')
                xml.set(fich.get_cand(cand), 'Motifs', motif)

        # On sauvegarde tous les fichiers retouchés
        for fich in list_fich_cand:
            fich.sauvegarde()