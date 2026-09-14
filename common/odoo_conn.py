import odoorpc

# CORRECCION 2026-09-14: el administrador de Odoo reporto sesiones RPC
# abiertas contra la base equivocada (usuario de PROD conectando a la DB de
# TEST y viceversa) - probablemente contribuyo a que se rompieran crons y
# dejaran de entrar mails. Causa raiz: para STAGE la instruccion historica
# era "conectar directo con odoorpc a mano" (mapeos_local.py pisa
# ODOO_URL/DB/USUARIO/CONTRASENA para apuntar todo a PROD, asi que
# conectar_odoo() nunca sirvio para stage) - eso llevo a que cada script
# suelto tipeara credenciales de stage a mano, en vez de usar una sola
# fuente revisada. Alcanza con UN typo/mezcla en una sola sesion para
# autenticarse contra la base equivocada.
#
# Arreglo: DOS funciones explicitas, con las credenciales puestas UNA sola
# vez cada una - conectar_odoo_prod() y conectar_odoo_stage(). Ningun
# script nuevo (de esta sesion o de cualquier otra) debe volver a tipear
# URL/DB/usuario/contraseña de Odoo sueltos en un script descartable -
# usar SIEMPRE estas dos funciones. Las dos verifican, despues de loguear,
# que la base a la que efectivamente se conectaron es la esperada - si no
# coincide, cortan con un error fuerte en vez de seguir operando calladas
# contra la base equivocada.

_PROD = {
    'url': 'prod17.odoo.imprentadiagonal.com.uy',
    'db': 'odoo17_prod',
    'login': 'ylan.archimowicz@imprentadiagonal.com.uy',
    'password': '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7',
}

_STAGE = {
    'url': 'testkrl.odoo.imprentadiagonal.com.uy',
    'db': 'odoo17_stage',
    'login': 'ylan.archimowicz@imprentadiagonal.com.uy',
    'password': '77436602dbb10c3959d3cf28e12e0cf4d253f667',
}


def _conectar(config, etiqueta):
    try:
        odoo = odoorpc.ODOO(
            config['url'],
            protocol='jsonrpc+ssl',
            port=443,
            timeout=120
        )
        odoo.login(
            config['db'],
            login=config['login'],
            password=config['password']
        )
        if odoo.env.db != config['db']:
            # Este chequeo es el punto entero de este archivo: si esto
            # dispara, es exactamente el bug que rompio los crons -
            # cortar aca, nunca devolver una conexion contra la base
            # equivocada en silencio.
            raise RuntimeError(
                f"CONEXION A LA BASE EQUIVOCADA: se pidio '{etiqueta}' "
                f"({config['db']}) pero la sesion quedo autenticada contra "
                f"'{odoo.env.db}'. Se corta la conexion, no se devuelve."
            )
        print(f"✅ Conexión a Odoo establecida con éxito ({etiqueta}: {config['db']}).")
        return odoo
    except Exception as e:
        print(f"❌ Error crítico al conectar con Odoo ({etiqueta}): {e}")
        return None


def conectar_odoo_prod():
    """Unica funcion para conectarse a PRODUCCION (prod17, odoo17_prod).
    Nunca tipear estas credenciales sueltas en otro script."""
    return _conectar(_PROD, 'PROD')


def conectar_odoo_stage():
    """Unica funcion para conectarse a STAGE (testkrl, odoo17_stage).
    Nunca tipear estas credenciales sueltas en otro script - este es el
    reemplazo de la vieja practica de armar el odoorpc.ODOO(...) a mano
    para stage en cada script descartable."""
    return _conectar(_STAGE, 'STAGE')


def conectar_odoo():
    """Compatibilidad retro: todo el codigo existente que ya llama
    conectar_odoo() sigue funcionando igual (apunta a PROD, como siempre -
    mapeos_local.py ya hacia esto antes). Codigo nuevo deberia llamar
    conectar_odoo_prod() o conectar_odoo_stage() explicitamente, sin
    ambiguedad de cual es cual."""
    return conectar_odoo_prod()
