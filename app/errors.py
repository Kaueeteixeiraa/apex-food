from flask import render_template


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, title="Acesso negado", message="Voce nao tem permissao para acessar esta area."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, title="Pagina nao encontrada", message="A tela solicitada nao existe."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", code=500, title="Erro interno", message="Nao foi possivel concluir a operacao agora."), 500
