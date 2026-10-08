"""The approved plain-language renderings, in Spanish.

A separate map rather than a fourth element on every clause tuple in
`forms_home`, `forms_auto` and `forms_home_long`. Three reasons:

* the English tuples are positional and long, and widening them in
  three files to add one field is a large diff with nothing to read in
  it;
* a translation pass over an approved English set is how a content
  owner actually works — one file, one reviewer, one sign-off; and
* a missing translation is then visibly missing, rather than an empty
  string buried in the middle of a nine-element tuple.

Keyed on `(form_number, heading)`, which is what identifies a clause to
a person. The same heading appears on several policies in the seeded
book; they share a rendering, exactly as the English ones do.

**What is not translated here:** form numbers, editions, page numbers
and dollar amounts. A form number is an identifier and $1,500 is
$1,500. The English wording of the form itself is not translated
anywhere — that is the binding text, and a translated exclusion is not
the exclusion.

Register: US Latin-American Spanish, second person formal ("usted"),
the same reading level the English renderings hold to. Written to be
read by a worried homeowner, not by a suscriptor.
"""

PLAIN_ES: dict[tuple[str, str], str] = {
    # ── HO 00 03, definitions ──────────────────────────────────────────
    ("HO 00 03", '"Bodily injury"'):
        "Lesión corporal significa que alguien resultó herido o enfermó, "
        "incluyendo lo que cuesta atenderlo, y la muerte si llega a ocurrir.",
    ("HO 00 03", '"Business"'):
        "Negocio es cualquier cosa que usted haga por dinero, de tiempo completo "
        "o de vez en cuando. Ganar menos de $2,000 en el año anterior al inicio "
        "de la póliza no cuenta; por encima de eso sí cuenta, y la actividad de "
        "negocio cambia lo que la póliza ampara.",
    ("HO 00 03", '"Occurrence"'):
        "Un suceso es un solo accidente. El daño que sigue pasando por la misma "
        "causa cuenta como un solo suceso, no como varios. Esto importa porque "
        "el límite se aplica por suceso.",
    ("HO 00 03", '"Residence premises"'):
        "La vivienda asegurada es la casa que aparece en su página de "
        "declaraciones y en la que usted realmente vive. Una propiedad que usted "
        "tiene pero no habita no entra en esta póliza.",

    # ── HO 00 03, property ─────────────────────────────────────────────
    ("HO 00 03", "Coverage A – Dwelling"):
        "La Cobertura A es la vivienda misma, o sea la casa, incluyendo lo que "
        "esté unido a ella, como un garaje o una terraza pegados. Lo máximo que "
        "pagamos por ella es el límite de Cobertura A de su página de "
        "declaraciones.",
    ("HO 00 03", "Coverage C – Personal Property"):
        "La Cobertura C son sus pertenencias: muebles, ropa, electrónicos, estén "
        "donde estén en el mundo. Las cosas que guarda en otra casa suya tienen "
        "un monto menor.",
    ("HO 00 03", "Special Limits Of Liability"):
        "Algunos tipos de bienes tienen su propio límite, mucho más bajo, cuando "
        "se los roban. Las joyas, los relojes y las pieles tienen un tope de "
        "$1,500 en total por un robo, no el límite completo de contenidos. Las "
        "armas de fuego y la platería tienen un tope de $2,500 cada una.",
    ("HO 00 03", "Coverage D – Loss Of Use"):
        "Si una pérdida amparada deja su casa inhabitable, pagamos el costo "
        "adicional de vivir en otro lugar: un hotel o una renta, y lo extra que "
        "gaste en comidas, para que su hogar siga funcionando mientras se hacen "
        "las reparaciones.",
    ("HO 00 03", "Accidental Discharge Or Overflow Of Water Or Steam"):
        "El agua que se escapa de repente de una tubería, un calentador, un aire "
        "acondicionado o un electrodoméstico dentro de la casa es un riesgo "
        "amparado. Una fuga lenta que lleva semanas o más no lo es.",
    ("HO 00 03", "Water Damage"):
        "La póliza base no ampara el agua que viene de afuera de la casa: "
        "inundación y agua de superficie, agua que se devuelve por alcantarillas "
        "o drenajes, agua que sale de una bomba de sumidero, y agua que sube "
        "desde debajo del suelo. Un complemento puede devolver parte de esto.",
    ("HO 00 03", "Earth Movement"):
        "Los terremotos, los deslizamientos, los hundimientos y cualquier otro "
        "movimiento del terreno no entran en esta póliza. El amparo por terremoto "
        "se compra aparte.",
    ("HO 00 03", "Limited Fungi, Wet Or Dry Rot, Or Bacteria Coverage"):
        "El moho y la pudrición tienen un amparo limitado, y solo hasta $10,000 "
        "por todo el año de la póliza, sin importar cuántos reclamos haga.",
    ("HO 00 03", "Your Duties After Loss"):
        "Después de cualquier pérdida usted debe avisarnos pronto, llamar a la "
        "policía si le robaron algo, evitar más daño cuando pueda hacerlo sin "
        "riesgo, guardar los bienes dañados para que puedan revisarse, y "
        "enviarnos una prueba de pérdida firmada dentro de los 60 días de que se "
        "la pidamos.",
    ("HO 00 03", "Debris Removal"):
        "La limpieza después de una pérdida amparada entra en el mismo límite, "
        "con un 5% adicional disponible si el daño más la limpieza lo superan.",
    ("HO 00 03", "Reasonable Repairs"):
        "Si usted gasta dinero para evitar que una pérdida amparada empeore, como "
        "tapiar una ventana o poner una lona en el techo, le pagamos eso. Guarde "
        "el recibo.",
    ("HO 00 03", "Coverage A and B – Open Perils"):
        "La casa y las otras estructuras tienen amparo contra cualquier cosa que "
        "las dañe físicamente, salvo lo que la póliza excluya de forma expresa. "
        "Eso es lo que significa un Formulario Especial: el trabajo lo hacen las "
        "exclusiones, no una lista de causas amparadas.",
    ("HO 00 03", "Coverage C – Named Perils"):
        "Sus pertenencias tienen amparo contra una lista específica de causas, no "
        "contra todo. Si la causa no está en la lista, la Cobertura C no "
        "responde. Esto es distinto de la casa misma.",
    ("HO 00 03", "Neglect"):
        "Si usted pudo haber evitado razonablemente que el daño empeorara y no lo "
        "hizo, esa parte no entra en la póliza.",
    ("HO 00 03", "Wear and Tear, Deterioration"):
        "La póliza paga accidentes repentinos, no cosas que se desgastan. El "
        "óxido, la pudrición, el asentamiento, las plagas y las fallas mecánicas "
        "son mantenimiento. Pero si algo de eso hace que una tubería gotee, el "
        "daño por esa agua sí entra.",
    ("HO 00 03", "Mold, Fungus or Wet Rot"):
        "El moho y la pudrición por lo general no entran en la póliza. La "
        "excepción es el moho escondido dentro de la estructura causado por una "
        "fuga de plomería, y ahí lo máximo que pagamos son $10,000 por todo el "
        "año de la póliza, sin importar cuántos reclamos haga.",
    ("HO 00 03", "Ordinance or Law"):
        "Si el código de construcción cambió desde que se construyó su casa, el "
        "costo de ponerla al código actual no entra en la póliza, salvo que usted "
        "haya comprado ese amparo aparte. Pagamos por dejarla como estaba.",
    ("HO 00 03", "Loss Settlement"):
        "El edificio se paga a lo que cuesta reconstruirlo, siempre que usted lo "
        "haya asegurado por al menos el 80% de ese valor. Sus pertenencias se "
        "pagan a lo que valían en ese momento, descontando su antigüedad, salvo "
        "que haya comprado amparo a valor de reposición para ellas.",
    ("HO 00 03", "Appraisal"):
        "Si no logramos ponernos de acuerdo en cuánto vale el daño, cualquiera de "
        "los dos puede pedir un avalúo. Usted elige un tasador, nosotros elegimos "
        "otro, y ellos eligen un tercero. El acuerdo de dos de los tres fija el "
        "monto.",
    ("HO 00 03", "Suit Against Us"):
        "Si usted quiere demandarnos por un reclamo, tiene dos años desde la "
        "fecha de la pérdida, y antes debe haber cumplido con lo que la póliza le "
        "pide.",

    # ── HO 00 03, liability ────────────────────────────────────────────
    ("HO 00 03", "Coverage E – Personal Liability"):
        "Si alguien se lastima o se daña su propiedad y usted es responsable "
        "legalmente, pagamos lo que usted debe hasta su límite, y pagamos un "
        "abogado, incluso si el reclamo resulta no tener fundamento.",
    ("HO 00 03", "Coverage F – Medical Payments To Others"):
        "Si una visita se lastima en su casa, pagamos sus cuentas médicas hasta "
        "el límite de Cobertura F, haya sido culpa suya o no. No aplica para "
        "usted ni para las personas que viven con usted.",
    ("HO 00 03", "Business Activities"):
        "Nada que surja de un negocio entra en la parte de responsabilidad civil "
        "de esta póliza. Rentar su casa de vez en cuando como vivienda es la "
        "excepción.",
    ("HO 00 03", "Motor Vehicle Liability"):
        "Todo lo que tenga que ver con un carro le corresponde a la póliza de "
        "auto, no a esta. Una podadora en la que uno se sienta y que solo se usa "
        "en su propio terreno, o un vehículo de movilidad, son la excepción.",
    ("HO 00 03", "Homeowners product guide – water losses"):
        "En general, las pólizas de hogar tratan el agua de adentro, el agua que "
        "se devuelve y el agua de inundación como tres cosas distintas. Lo que "
        "diga su propia póliza depende de los complementos que tenga adjuntos.",

    # ── HO 04 95, water back-up ────────────────────────────────────────
    ("HO 04 95", "Water Back-Up And Sump Discharge Or Overflow"):
        "Este complemento devuelve a su amparo el retorno de alcantarillas y "
        "drenajes. Si el agua se devuelve por una alcantarilla o un drenaje, o se "
        "desborda de su bomba de sumidero, el daño que le hace a su casa y a sus "
        "pertenencias entra hasta el límite que muestra este complemento.",
    ("HO 04 95", "Limit Of Liability And Deductible"):
        "Hay un límite aparte y un deducible aparte para las pérdidas por "
        "retorno de agua, ambos en su página de declaraciones. No se suman a sus "
        "otros límites.",
    ("HO 04 95", "What This Endorsement Does Not Cover"):
        "Este complemento ampara solo el retorno de agua. El agua que llega como "
        "inundación o como agua de superficie desde afuera sigue fuera de la "
        "póliza; para eso hace falta un seguro de inundación aparte.",
    ("HO 04 95", "What is added"):
        "Esto devuelve la parte de alcantarilla y sumidero de la exclusión de "
        "agua. Si el agua se devuelve por una alcantarilla o un drenaje, o se "
        "desborda de su bomba de sumidero, entra hasta el límite indicado para "
        "este complemento, incluso cuando la bomba simplemente falló.",
    ("HO 04 95", "What is still excluded"):
        "Esto no lo convierte en un seguro de inundación. El agua que llega de "
        "afuera, de un río, del mar o de la superficie después de una tormenta, "
        "sigue excluida, y también el daño de una bomba que usted sabía que "
        "estaba dañada y dejó así.",

    # ── HO 03 12, wind and hail ────────────────────────────────────────
    ("HO 03 12", "Windstorm Or Hail Percentage Deductible"):
        "El daño por viento y granizo tiene su propio deducible, calculado como "
        "un porcentaje de su límite de Cobertura A y no como una cantidad fija en "
        "dólares. Reemplaza su deducible normal para ese tipo de daño, así que "
        "suele ser más alto.",
    ("HO 03 12", "How it is worked out"):
        "Para viento o granizo, su deducible es un porcentaje del límite de "
        "Cobertura A en vez de una cantidad fija, y reemplaza su deducible normal "
        "para ese reclamo. Se calcula sobre el límite, no sobre cuánto fue el "
        "daño.",

    # ── HO 04 61, scheduled property ───────────────────────────────────
    ("HO 04 61", "Scheduled Personal Property"):
        "Cualquier cosa listada en este anexo, por ejemplo un anillo o un reloj "
        "con nombre, tiene amparo por el monto que aparece a su lado, sin "
        "deducible, en lugar de caer bajo el tope especial de $1,500 por robo de "
        "joyas.",
    ("HO 04 61", "What a schedule does"):
        "Lo que está en el anexo tiene amparo por el monto indicado frente a casi "
        "cualquier causa, sin deducible, y los topes normales de Cobertura C para "
        "joyas y artículos parecidos no se le aplican.",

    # ── HO 01 41, Texas ────────────────────────────────────────────────
    ("HO 01 41", "Texas – Appraisal And Notice Of Claim"):
        "En Texas, si usted y la aseguradora no se ponen de acuerdo en cuánto "
        "vale una pérdida, cualquiera de las dos partes puede pedir un avalúo. "
        "Cada parte elige entonces su propio tasador dentro de 20 días.",
    ("HO 01 41", "Windstorm in a catastrophe area"):
        "En la costa de Texas, el amparo por viento y granizo depende de que la "
        "propiedad tenga un certificado de cumplimiento. Sin ese certificado, el "
        "daño por viento no entra en esta póliza.",
    ("HO 01 41", "Prompt payment of claims"):
        "En Texas debemos acusar recibo de su reclamo dentro de 15 días, decirle "
        "por escrito si se acepta dentro de 15 días hábiles desde que recibimos "
        "todo lo que pedimos, y pagar dentro de 5 días hábiles después de "
        "aceptarlo.",

    # ── PP 00 01, personal auto ────────────────────────────────────────
    ("PP 00 01", "Insuring Agreement"):
        "Si usted es responsable legalmente de lesionar a alguien o de dañar su "
        "propiedad en un accidente de carro, esta parte paga lo que usted les "
        "debe, hasta su límite de responsabilidad, y paga su defensa.",
    ("PP 00 01", "Exclusions – Public Or Livery Conveyance"):
        "Conducir por dinero, llevando pasajeros que pagan o haciendo entregas "
        "para un servicio, no entra en la póliza estándar. Compartir el costo de "
        "un viaje con alguien a quien iba a llevar de todos modos sí está bien.",
    ("PP 00 01", "Other Than Collision"):
        "El daño que no es un choque, como robo, incendio, granizo, un parabrisas "
        "estrellado, atropellar a un venado, vandalismo o inundación, entra por "
        "cobertura amplia, y se aplica el deducible de esa cobertura.",
    ("PP 00 01", "Transportation Expenses"):
        "Mientras su carro está fuera de circulación después de una pérdida "
        "amparada, la póliza aporta para un carro de alquiler y otros traslados, "
        "hasta $600 en total. Empieza 24 horas después de la pérdida, o 48 horas "
        "después de un robo, y termina cuando su carro vuelve o se paga.",
    ("PP 00 01", "Personal auto product guide – deductibles"):
        "El amparo de daños a su propio carro tiene deducibles: uno para choques "
        "y otro para todo lo demás. El amparo de responsabilidad civil, que paga "
        "a otras personas, no tiene deducible.",

    # ── PP 03 06 and PP 01 89 ──────────────────────────────────────────
    ("PP 03 06", "Extended Transportation Expenses"):
        "Si usted compró este complemento, su amparo de carro de alquiler es el "
        "monto diario y el número de días que aparecen en su página de "
        "declaraciones, en lugar del total estándar de $600.",
    ("PP 01 89", "Texas – Prompt Payment Of Claims"):
        "En Texas, una vez que tengamos todo lo que pedimos, debemos decirle por "
        "escrito si el reclamo se acepta o se rechaza dentro de 15 días hábiles.",
}


def for_clause(form_number: str, heading: str) -> str:
    """The Spanish rendering, or an empty string.

    Empty is a real answer: it means this clause has no approved Spanish
    wording yet, and the composer will say so rather than quietly
    delivering English inside a Spanish answer.
    """
    return PLAIN_ES.get((form_number, heading), "")
