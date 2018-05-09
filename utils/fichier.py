#!/usr/bin/env python3
#-*- coding: utf-8 -*-

# Ce fichier contient la classe Fichier.
###
#   Contient le contenu (dossiers) d'un fichier dont le nom est
#   passé au constructeur.
#   Réuni toutes les méthodes agissant sur ces dossiers et celles
#   qui agissent sur le contenu des dossiers : les candidatures.
###

from parse import parse
from lxml import etree
from utils.parametres import filieres
from utils.parametres import coef_cpes
from utils.parametres import coef_term
from utils.parametres import prop_ecrit_EAF 
from utils.parametres import prop_prem_trim
from utils.toolbox import *

#################################################################################
#                               Fichier                                         #
#################################################################################
class Fichier(object):
    """ objet fichier : son but est de contenir toutes les méthodes qui agissent
    sur le contenu des fichiers, i.e. les dossiers de candidatures. Ces fichiers
    sont des attributs des objets 'Client' que gère l'objet 'Serveur'."""

    ############# Méthodes de classe ##############
    @classmethod
    def get(cls, cand, attr):
        """ accesseur : récupère le contenu d'un noeud xml
         cand est un etree.Element pointant un candidat
         attr est une clé du dictionnaire 'acces' défini ci-dessus """
        try:
            result = cand.xpath(Fichier.acces[attr]['query'])[0].text
            if 'post' in Fichier.acces[attr].keys():
                result = Fichier.acces[attr]['post'](result)
            if not(result): result = Fichier.acces[attr]['defaut'] # évite un retour None si le champ est <blabla/>
        except:
            result = Fichier.acces[attr]['defaut']
        return result

    @classmethod
    def set(cls, cand, attr, value):
        """ mutateur : écrit le contenu d'un noeud xml
         cand est un etree.Element pointant un candidat
         attr est une clé du dictionnaire 'acces' défini ci-dessus
         value est la valeur à écrire dans le noeud choisi.
         Si le noeud n'existe pas, la fonction accro_branch (ci-après) """
        query = Fichier.acces[attr]['query']
        if 'pre' in Fichier.acces[attr].keys():
            value = Fichier.acces[attr]['pre'](value)
        try:
            cand.xpath(query)[0].text = value
        except:
            node = query.split('/')[-1]
            fils = etree.Element(node)
            fils.text = value
            pere = parse('{}/' + node, query)[0]
            cls._accro_branche(cand, pere, fils)

    @classmethod
    def _accro_branche(cls, cand, pere, fils):
        """ Reconstruction d'une arborescence incomplète. On procède
        de manière récursive en commençant par l'extrémité (les feuilles !)...
        pere est un chemin (xpath) et fils un etree.Element
        ATTENTION : il ne faut pas d'espaces superflues dans la chaine pere. """
        if cand.xpath(pere) != []: # test si pere est une branche existante
            cand.xpath(pere)[0].append(fils) # si oui, on accroche le fils
        else: # sinon on créé le père et on va voir le grand-père
            node = pere.split('/')[-1] # récupération du dernier champ du chemin
            if 'Chimie' in node: node=pere.split('/')[-2]+'/'+node # un traitement
            # particulier du fait que le champ contient '/' (Physique/Chimie)
            grand_pere = parse('{}/' + node, pere)[0] # le reste du chemin est le grand-pere
            # analyse et création du père avec tous ses champs...
            noeuds = parse('{}[{}]', node)
            if noeuds is None:
                noeuds = [node]
            pere = etree.Element(noeuds[0])
            if noeuds != [node]: # le père a d'autres enfants
                list = noeuds[1].split('][')
                for li in list:
                    dico = parse('{nom}="{val}"', li)
                    el = etree.Element(dico['nom'])
                    el.text = dico['val']
                    pere.append(el)
            pere.append(fils)
            _accro_branche(cand, grand_pere, pere)

    @classmethod
    def is_complet(cls, cand):
        """ La synthèse (notes de 1e, Tle, bac français, etc.) est elle complète ? booléen """
        # Construction de la liste des champs à vérifier
        champs = set([])
        matiere = ['Mathématiques', 'Physique/Chimie']
        # Première
        classe = 'Première'
        date = ['trimestre 1', 'trimestre 2', 'trimestre 3']
        for mat in matiere:
            for da in date:
                champs.add('{} Première {}'.format(mat , da))
        # Terminale
        classe = 'Terminale'
        date = ['trimestre 1', 'trimestre 2']
        if 'cpes' in Fichier.get(cand, 'Classe actuelle').lower():
            date.append('trimestre 3')
        for mat in matiere:
            for da in date:
                champs.add('{} Terminale {}'.format(mat , da))
        # CPES
        if 'cpes' in Fichier.get(cand, 'Classe actuelle').lower():
            champs.add('Mathématiques CPES')
            champs.add('Physique/Chimie CPES')
        # EAF
        champs.add('Écrit EAF')
        champs.add('Oral EAF')
        # Test :
        complet = not(cls.get(cand, 'Classe actuelle') == '?') # une initialisation astucieuse..
        while (complet and len(champs) > 0):
            ch = champs.pop()
            if cls.get(cand, ch) == '-': # '-' est la valeur par défaut d'une note..
                complet = False
        return complet

    @classmethod
    def calcul_scoreb(cls, cand):
        """ Calcul du score brut et renseignement du noeud xml """
        # Si correc = 'NC', cela signifie que l'admin rejette le dossier : scoreb = 0
        scoreb = vers_str(0) # valeur si correc = 'NC'
        if cls.get(cand, 'Correction') != 'NC':
            # Récupération des coef
            if 'cpes' in cls.get(cand, 'Classe actuelle').lower(): 
                coef = coef_cpes
            else:
                coef = coef_term
            # moyenne de première
            tot = 0
            nb = 0
            matiere = ['Mathématiques', 'Physique/Chimie']
            trim = ['trimestre 1','trimestre 2','trimestre 3']
            for t in trim:
                for mat in matiere:
                    key = '{} Première {}'.format(mat, t)
                    note = cls.get(cand, key)
                    if note != '-':
                        tot += vers_num(note)
                        nb += 1
            if nb > 0:
                moy_prem = tot/nb
            else:
                moy_prem = 0
            # moyenne de terminale
            tot = 0
            nb = 0
            if coef['cpes']: # candidat en cpes (poids uniforme)
                trim = ['trimestre 1','trimestre 2','trimestre 3']
                for t in trim:
                    for mat in matiere:
                        key = '{} Terminale {}'.format(mat, t)
                        note = cls.get(cand, key)
                        if note != '-':
                            tot += vers_num(note)
                            nb += 1
                if nb > 0:
                    moy_term = tot/nb
                else:
                    moy_term = 0
            else: # candidat en terminale : 45% 1er trimestre ; 55% 2e trimestre (config dans parametre.py)
                if cls.get(cand, 'sem_term') == 'on':
                    for mat in matiere:
                        key = '{} Terminale trimestre 1'.format(mat)
                        note = cls.get(cand, key)
                        if note != '-':
                            tot += vers_num(note)
                            nb += 1
                else:
                    trim = ['trimestre 1','trimestre 2']
                    for t in trim:
                        for mat in matiere:
                            key = '{} Terminale {}'.format(mat, t)
                            note = cls.get(cand, key)
                            if note != '-':
                                if '1' in t:
                                    tot += vers_num(note)*prop_prem_trim
                                    nb += prop_prem_trim 
                                else:
                                    tot+= vers_num(note)*(1-prop_prem_trim)
                                    nb += 1-prop_prem_trim
                if nb > 0:
                    moy_term = tot/nb
                else:
                    moy_term = 0
            # moyenne EAF : 2/3 pour l'écrit et 1/3 pour l'oral
            tot = 0
            nb = 0
            note = cls.get(cand, 'Écrit EAF')
            if note != '-':
                tot += vers_num(note)*prop_ecrit_EAF
                nb += prop_ecrit_EAF
            note = cls.get(cand, 'Oral EAF')
            if note != '-':
                tot += vers_num(note)*(1-prop_ecrit_EAF)
                nb += 1-prop_ecrit_EAF
            if nb > 0:
                moy_EAF = tot/nb
            else:
                moy_EAF = 0
            # éventuellement moyenne de CPES
            if coef['cpes']: # candidat en cpes
                tot = 0
                nb = 0
                keys = ['Mathématiques CPES', 'Physique/Chimie CPES']
                for key in keys:
                    note = cls.get(cand, key)
                    if note != '-':
                        tot += vers_num(note)
                        nb += 1
                if nb > 0:
                    moy_cpes = tot/nb
                else:
                    moy_cpes = 0
            # score brut
            tot = moy_prem*coef['Première'] + moy_term*coef['Terminale'] + moy_EAF*coef['EAF']
            nb = coef['Première'] + coef['Terminale'] + coef['EAF']
            if coef['cpes']:
                tot += moy_cpes*coef['cpes']
                nb += coef['cpes']
            scoreb = vers_str(tot/nb)
        cls.set(cand, 'Score brut', scoreb)
            
    @classmethod
    def rang(cls, cand, dossiers, critere):
        """ Trouver le rang d'un candidat dans une liste de dossiers, selon un critère donné """
        rg = 1
        score_actu = cls.get(cand, critere)
        if dossiers:
            while (rg <= len(dossiers) and cls.get(dossiers[rg-1], critere) > score_actu):
                rg+= 1
        return rg
    #                                             #
    ############ Fin méthodes de classe ###########

    ############## Attributs de classe #############
    ## _criteres_tri : contient les fonctions qui sont les clés de tri de la méthode
    # 'ordonne' définie plus bas..
    _criteres_tri = {
            'score_b' : lambda cand: -float(Fichier.get(cand, 'Score brut').replace(',','.')),
            'score_f' : lambda cand: -Fichier.get(cand, 'Score final num'),
            'alpha' : lambda cand: Fichier.get(cand, 'Nom')
            }

    ## acces : dictionnaire contenant les clés d'accès aux informations candidat
    # L'argument est encore un dictionnaire :
    # Celui-ci DOIT contenir :
    #       une clé 'query' pointant sur le path xml,
    #       une clé 'defaut' pointant sur la valeur à renvoyer par défaut.
    # et il PEUT contenir :
    #       une clé 'pre' pointant sur une fonction de pré-traitement (avant set),
    #       une clé 'post' pointant sur une fonction de post-traitement (après get).
    acces = {\
            'Nom'               : {'query' : 'nom', 'defaut' : '?'},
            'Prénom'            : {'query' : 'prénom', 'defaut' : '?'},
            'Sexe'              : {'query' : 'sexe', 'defaut' : '?'},
            'Date de naissance' : {'query' : 'naissance', 'defaut' : '?'},
            'Classe actuelle'   : {'query' : 'synoptique/classe', 'defaut' : '?'},
            'Num ParcoursSup'   : {'query' : 'id_apb', 'defaut' : '?'},
            'INE'               : {'query' : 'INE', 'defaut' : '?'},
            'Nationalité'       : {'query' : 'nationalité', 'defaut' : '?'},
            'Boursier'          : {'query' : 'boursier', 'defaut' : '?'},
            'Boursier certifié' : {'query' : 'boursier_certifie', 'defaut' :'?'},
            'Établissement'     : {'query' : 'synoptique/établissement/nom', 'defaut' : '?'},
            'Commune'           : {'query' : 'synoptique/établissement/ville', 'defaut' : '?'},
            'Département'       : {'query' : 'synoptique/établissement/département', 'defaut' : '?'},
            'Pays'              : {'query' : 'synoptique/établissement/pays', 'defaut' : '?'},
            'Écrit EAF'         : {'query' : 'synoptique/français.écrit', 'defaut' : '-', 'pre' : not_note, 'post' : 
                convert},
            'Oral EAF'          : {'query' : 'synoptique/français.oral', 'defaut' : '-', 'pre' : not_note, 'post' : 
                convert},
            'Candidatures'      : {'query' : 'diagnostic/candidatures', 'defaut' : '???', 'pre' : formate_candid},
            'Candidatures impr' : {'query' : 'diagnostic/candidatures', 'defaut' : '???', 'post' : formate_impr_candid},
            'sem_prem'          : {'query' : 'diagnostic/sem_prem', 'defaut' : 'off'},
            'sem_term'          : {'query' : 'diagnostic/sem_term', 'defaut' : 'off'},
            'traité'            : {'query' : 'diagnostic/traité', 'defaut' : False},
            'Jury'              : {'query' : 'diagnostic/jury', 'defaut' : 'Auto', 'pre' : formate_jury},
            'Motifs'            : {'query' : 'diagnostic/motifs', 'defaut' : ''},
            'Score brut'        : {'query' : 'diagnostic/score', 'defaut' : ''},
            'Correction'        : {'query' : 'diagnostic/correc', 'defaut' : '0'},
            'Score final'       : {'query' : 'diagnostic/scoref', 'defaut' : ''},
            'Score final num'   : {'query' : 'diagnostic/scoref', 'defaut' : 0, 'post' : num_score},
            'Rang brut'         : {'query' : 'diagnostic/rangb', 'defaut' : '?'},
            'Rang final'        : {'query' : 'diagnostic/rangf', 'defaut' : '?'}
            }
    # Pour les notes du lycée :
    matiere = ['Mathématiques', 'Physique/Chimie']
    date = ['trimestre 1', 'trimestre 2', 'trimestre 3']
    classe = ['Première', 'Terminale']
    for cl in classe:
        for mat in matiere:
            for da in date:
                key = '{} {} {}'.format(mat, cl, da)
                query = 'bulletins/bulletin[classe="{}"]/matières/matière[intitulé="{}"][date="{}"]/note'.format(\
                        cl, mat, da)
                acces[key] = {'query' : query, 'defaut' : '-', 'pre' : not_note, 'post' : convert}
    # Pour les notes CPES :
    for mat in matiere:
        key = '{} CPES'.format(mat)
        query = 'synoptique/matières/matière[intitulé="{}"]/note'.format(mat)
        acces[key] = {'query' : query, 'defaut' : '-', 'pre' : not_note, 'post' : convert}
    ############## Fin attributs de classe ########

    ############# Méthodes d'instance #############
    #                                             #
    def __init__(self, nom):
        """ Constructeur """
        # stockage du nom
        self.nom = nom
        # A priori, il n'est pas nécessaire de vérifier que le
        # fichier 'nom' existe, cela a été fait avant la construction
        parser = etree.XMLParser(remove_blank_text=True) # pour que pretty_print fonctionne
        self._dossiers = etree.parse(nom, parser).getroot()
        # On créé aussi l'ensemble (set) des identifiants des candidats
        self._identif = {Fichier.get(cand, 'Num ParcoursSup') for cand in self._dossiers}
        # On récupère la filière. Utilisation d'un set pour éviter les doublons !
        self._filiere = {fil for fil in filieres if fil in nom.lower()}.pop()

    def __iter__(self):
        """ Cette méthode fait d'un objet fichier un itérable (utilisable dans une boucle)
        Cela sert à créer la liste de dossiers qui apparaît dans la page html de traitement
        On itère sur la liste de dossiers que contient le fichier. """
        return self._dossiers.__iter__()

    def __contains__(self, cand):
        """ méthode qui implémente l'opérateur 'in'.
        la syntaxe est 'if cand in objet_Fichier'
        dans laquelle cand est un noeud xml pointant sur un candidat.
        Elle retourne un booléen. Utile pour l'admin qui traite un
        candidat et reporte dans toutes les filières demandées. """
        return Fichier.get(cand, 'Num ParcoursSup') in self._identif
    
    def __len__(self):
        """ Cette méthode confère un sens à l'opération len(fichier) """
        return len(self._dossiers)

    def cand(self, index):
        """ Renvoie le noeud candidat indexé par 'index' dans self._dossiers """
        return self._dossiers[index]

    def get_cand(self, cand):
        """ Renvoie le candidat dont l'identifiant est identique à celui de cand """
        # Ne sert qu'à l'admin quand il traite un candidat sur une filière
        # et REPORTE ses modifs dans toutes les filières demandées..
        # Sert aussi à la fonction stat() dans la toolbox.
        # À n'utiliser que sur des fichiers contenant le candidat ('cand in fichier' True)
        # Utile de la rendre plus robuste (gérer l'erreur si 'cand in fichier' False) ?
        index = 0
        while Fichier.get(cand, 'Num ParcoursSup') != Fichier.get(self._dossiers[index], 'Num ParcoursSup'):
            index += 1
        return self._dossiers[index]

    def filiere(self):
        """ renvoie la filière """
        return self._filiere

    def convert(self, naiss):
        """ Convertit une date de naissance en un nombre pour le classement """
        dic = parse('{j:d}/{m:d}/{a:d}', naiss)
        return dic['a']*10**4 + dic['m']*10**2 + dic['j']

    def ordonne(self, critere):
        """ renvoie une liste des candidatures ordonnées selon le critère demandé
        (critère appartenant à l'attribut de classe _critere_tri) """
        # Classement par age
        doss = sorted(self._dossiers, key = lambda cand: self.convert(cand.xpath('naissance')[0].text))
        # puis par critere
        return sorted(doss, key = Fichier._criteres_tri[critere])

    def sauvegarde(self):
        """ Sauvegarde le fichier : mise à jour (par écrasement) du fichier xml """
        with open(self.nom, 'wb') as fich:
            fich.write(etree.tostring(self._dossiers, pretty_print=True, encoding='utf-8'))

