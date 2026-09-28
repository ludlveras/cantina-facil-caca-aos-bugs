import os
import sqlite3
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# Caminho absoluto para evitar erros no servidor Linux do Render
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static')
)

app.secret_key = "cantina-facil-2026"
DATABASE = os.path.join(base_dir, "cantina.db")


def conectar():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def inicializar_banco():
    conexao = conectar()

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            nome TEXT NOT NULL
        )
    """)

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL,
            estoque INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 5,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            total REAL NOT NULL,
            pagamento TEXT NOT NULL
        )
    """)

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS itens_venda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)

    usuario = conexao.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        ("admin",)
    ).fetchone()

    if not usuario:
        conexao.execute(
            """
            INSERT INTO usuarios (usuario, senha, nome)
            VALUES (?, ?, ?)
            """,
            ("admin", "1234", "Administrador")
        )

    quantidade_produtos = conexao.execute(
        "SELECT COUNT(*) AS total FROM produtos"
    ).fetchone()["total"]

    if quantidade_produtos == 0:
        produtos = [
            ("Coxinha", "Salgados", 6.00, 30, 10),
            ("Pastel", "Salgados", 7.00, 20, 5),
            ("Refrigerante", "Bebidas", 5.00, 40, 10),
            ("Suco", "Bebidas", 4.00, 25, 8),
            ("Água", "Bebidas", 3.00, 50, 10),
            ("Brigadeiro", "Doces", 3.50, 15, 5)
        ]

        conexao.executemany(
            """
            INSERT INTO produtos
            (nome, categoria, preco, estoque, estoque_minimo)
            VALUES (?, ?, ?, ?, ?)
            """,
            produtos
        )

    conexao.commit()
    conexao.close()


def login_obrigatorio(funcao):
    @wraps(funcao)
    def verificar_login(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return verificar_login


def buscar_produtos(busca=""):
    conexao = conectar()

    if busca:
        produtos = conexao.execute(
            """
            SELECT *
            FROM produtos
            WHERE nome LIKE ?
            ORDER BY nome
            """,
            (f"%{busca}%",)
        ).fetchall()
    else:
        produtos = conexao.execute(
            """
            SELECT *
            FROM produtos
            ORDER BY nome
            """
        ).fetchall()

    conexao.close()

    return produtos


@app.route("/")
def inicio():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        conexao = conectar()

        dados = conexao.execute(
            """
            SELECT id, usuario, senha, nome
            FROM usuarios
            WHERE usuario = ?
            """,
            (usuario,)
        ).fetchone()

        conexao.close()

        if dados and dados["senha"] == senha:
            session["usuario_id"] = dados["id"]
            session["usuario_nome"] = dados["nome"]

            return redirect(url_for("dashboard"))

        erro = "Usuário ou senha inválidos."

    return render_template(
        "login.html",
        erro=erro
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_obrigatorio
def dashboard():
    conexao = conectar()

    total_produtos = conexao.execute(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE ativo = 1
        """
    ).fetchone()[0]

    hoje = date.today().isoformat()

    vendas_hoje = conexao.execute(
        """
        SELECT COUNT(*)
        FROM vendas
        WHERE DATE(data) = ?
        """,
        (hoje,)
    ).fetchone()[0]

    faturamento = conexao.execute(
        """
        SELECT COALESCE(SUM(total), 0)
        FROM vendas
        WHERE DATE(data) = ?
        """,
        (hoje,)
    ).fetchone()[0]

    estoque_baixo = conexao.execute(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE ativo = 1
        AND estoque <= estoque_minimo
        """
    ).fetchone()[0]

    ultimas_vendas = conexao.execute(
        """
        SELECT id, data, total, pagamento
        FROM vendas
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    conexao.close()

    return render_template(
        "dashboard.html",
        total_produtos=total_produtos,
        vendas_hoje=vendas_hoje,
        faturamento=faturamento,
        estoque_baixo=estoque_baixo,
        ultimas_vendas=ultimas_vendas
    )


@app.route("/produtos")
@login_obrigatorio
def produtos():
    busca = request.args.get("busca", "").strip()
    lista = buscar_produtos(busca)

    mensagem = request.args.get("mensagem")
    erro = request.args.get("erro")

    return render_template(
        "produtos.html",
        produtos=lista,
        busca=busca,
        mensagem=mensagem,
        erro=erro
    )


@app.route("/produtos/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo_produto():
    erro = None

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "").strip()
        preco = request.form.get("preco", "").strip()
        estoque = request.form.get("estoque", "").strip()
        estoque_minimo = request.form.get("estoque_minimo", "").strip()

        if not nome or not categoria or not preco or not estoque:
            erro = "Preencha todos os campos obrigatórios."
        else:
            try:
                preco = float(preco)
                estoque = int(estoque)
                estoque_minimo = int(estoque_minimo or 0)

                if preco <= 0:
                    erro = "O preço deve ser maior que zero."

                elif estoque < 0:
                    erro = "O estoque não pode ser negativo."

                else:
                    conexao = conectar()

                    conexao.execute(
                        """
                        INSERT INTO produtos
                        (nome, categoria, preco, estoque, estoque_minimo)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            nome,
                            categoria,
                            preco,
                            estoque,
                            estoque_minimo
                        )
                    )

                    conexao.commit()
                    conexao.close()

                    return redirect(
                        url_for(
                            "produtos",
                            mensagem="Produto cadastrado com sucesso."
                        )
                    )

            except ValueError:
                erro = "Valores numéricos inválidos."

    return render_template(
        "produto_form.html",
        produto=None,
        erro=erro
    )


@app.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_produto(produto_id):
    conexao = conectar()

    produto = conexao.execute(
        """
        SELECT *
        FROM produtos
        WHERE id = ?
        """,
        (produto_id,)
    ).fetchone()

    conexao.close()

    if not produto:
        return redirect(
            url_for(
                "produtos",
                erro="Produto não encontrado."
            )
        )

    erro = None

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "").strip()
        preco = request.form.get("preco", "").strip()
        estoque = request.form.get("estoque", "").strip()
        estoque_minimo = request.form.get("estoque_minimo", "").strip()
        ativo = 1 if request.form.get("ativo") == "1" else 0

        try:
            preco = float(preco)
            estoque = int(estoque)
            estoque_minimo = int(estoque_minimo or 0)

            if not nome or not categoria:
                erro = "Nome e categoria são obrigatórios."

            elif preco < 0:
                erro = "Preço inválido."

            elif estoque < 0:
                erro = "Estoque inválido."

            else:
                conexao = conectar()

                conexao.execute(
                    """
                    UPDATE produtos
                    SET nome = ?,
                        categoria = ?,
                        preco = ?,
                        estoque = ?,
                        estoque_minimo = ?,
                        ativo = ?
                    WHERE id = ?
                    """,
                    (
                        nome,
                        categoria,
                        preco,
                        estoque,
                        estoque_minimo,
                        ativo,
                        produto_id
                    )
                )

                conexao.commit()
                conexao.close()

                return redirect(
                    url_for(
                        "produtos",
                        mensagem="Produto atualizado com sucesso."
                    )
                )

        except ValueError:
            erro = "Valores numéricos inválidos."

    return render_template(
        "produto_form.html",
        produto=produto,
        erro=erro
    )


@app.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
@login_obrigatorio
def excluir_produto(produto_id):
    conexao = conectar()

    produto = conexao.execute(
        """
        SELECT id
        FROM produtos
        WHERE id = ?
        """,
        (produto_id,)
    ).fetchone()

    if not produto:
        conexao.close()

        return redirect(
            url_for(
                "produtos",
                erro="Produto não encontrado."
            )
        )

    quantidade_vendas = conexao.execute(
        """
        SELECT COUNT(*)
        FROM itens_venda
        WHERE produto_id = ?
        """,
        (produto_id,)
    ).fetchone()[0]

    if quantidade_vendas > 0:
        conexao.execute(
            """
            UPDATE produtos
            SET ativo = 0
            WHERE id = ?
            """,
            (produto_id,)
        )
    else:
        conexao.execute(
            """
            DELETE FROM produtos
            WHERE id = ?
            """,
            (produto_id,)
        )

    conexao.commit()
    conexao.close()

    return redirect(
        url_for(
            "produtos",
            mensagem="Produto excluído com sucesso."
        )
    )


@app.route("/vendas")
@login_obrigatorio
def vendas():
    conexao = conectar()

    produtos = conexao.execute(
        """
        SELECT id, nome, preco, estoque
        FROM produtos
        WHERE ativo = 1
        AND estoque > 0
        ORDER BY nome
        """
    ).fetchall()

    conexao.close()

    return render_template(
        "vendas.html",
        produtos=produtos
    )


@app.route("/vendas/nova", methods=["POST"])
@login_obrigatorio
def nova_venda():
    produtos_ids = request.form.getlist("produto_id[]")
    quantidades = request.form.getlist("quantidade[]")
    pagamento = request.form.get("pagamento", "").strip()

    if not produtos_ids or not quantidades:
        return render_template(
            "vendas.html",
            produtos=buscar_produtos(),
            erro="Adicione pelo menos um produto."
        )

    if pagamento not in [
        "Dinheiro",
        "PIX",
        "Cartão de débito",
        "Cartão de crédito"
    ]:
        return render_template(
            "vendas.html",
            produtos=buscar_produtos(),
            erro="Forma de pagamento inválida."
        )

    if len(produtos_ids) != len(quantidades):
        return render_template(
            "vendas.html",
            produtos=buscar_produtos(),
            erro="Dados da venda inválidos."
        )

    conexao = conectar()

    itens = []
    total = 0

    try:
        for produto_id, quantidade in zip(produtos_ids, quantidades):
            produto = conexao.execute(
                """
                SELECT id, nome, preco, estoque
                FROM produtos
                WHERE id = ?
                AND ativo = 1
                """,
                (produto_id,)
            ).fetchone()

            if not produto:
                raise ValueError("Produto não encontrado.")

            quantidade = int(quantidade)

            if quantidade < 0:
                raise ValueError("Quantidade inválida.")

            if quantidade > produto["estoque"]:
                raise ValueError(
                    f"Estoque insuficiente para {produto['nome']}."
                )

            subtotal = produto["preco"] + quantidade
            total += subtotal

            itens.append({
                "produto_id": produto["id"],
                "quantidade": quantidade,
                "preco": produto["preco"],
                "subtotal": subtotal
            })

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = conexao.execute(
            """
            INSERT INTO vendas
            (data, total, pagamento)
            VALUES (?, ?, ?)
            """,
            (
                agora,
                total,
                pagamento
            )
        )

        venda_id = cursor.lastrowid

        for item in itens:
            conexao.execute(
                """
                INSERT INTO itens_venda
                (venda_id, produto_id, quantidade, preco_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    venda_id,
                    item["produto_id"],
                    item["quantidade"],
                    item["preco"],
                    item["subtotal"]
                )
            )

            conexao.execute(
                """
                UPDATE produtos
                SET estoque = estoque - ?
                WHERE id = ?
                """,
                (
                    item["quantidade"],
                    item["produto_id"]
                )
            )
        conexao.commit()
        conexao.close()

        return redirect(
            url_for(
                "dashboard",
                mensagem="Pedido realizado com sucesso!"
            )
        )

    except (ValueError, TypeError):
        conexao.rollback()
        conexao.close()

        return render_template(
            "vendas.html",
            produtos=buscar_produtos(),
            erro="Não foi possível realizar a venda."
        )


@app.route("/estoque")
@login_obrigatorio
def estoque():
    conexao = conectar()

    produtos = conexao.execute(
        """
        SELECT *
        FROM produtos
        WHERE ativo = 1
        ORDER BY nome
        """
    ).fetchall()

    total_produtos = conexao.execute(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE ativo = 1
        """
    ).fetchone()[0]

    total_estoque = conexao.execute(
        """
        SELECT COALESCE(SUM(estoque), 0)
        FROM produtos
        WHERE ativo = 1
        """
    ).fetchone()[0]

    produtos_baixos = conexao.execute(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE ativo = 1
        AND estoque <= estoque_minimo
        """
    ).fetchone()[0]

    conexao.close()

    return render_template(
        "estoque.html",
        produtos=produtos,
        total_produtos=total_produtos,
        total_estoque=total_estoque,
        produtos_baixos=produtos_baixos,
        mensagem=request.args.get("mensagem"),
        erro=request.args.get("erro")
    )


@app.route("/estoque/<int:produto_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_estoque(produto_id):
    conexao = conectar()

    produto = conexao.execute(
        """
        SELECT *
        FROM produtos
        WHERE id = ?
        """,
        (produto_id,)
    ).fetchone()

    conexao.close()

    if not produto:
        return redirect(
            url_for(
                "estoque",
                erro="Produto não encontrado."
            )
        )

    if request.method == "POST":
        quantidade = request.form.get("quantidade", "").strip()

        try:
            quantidade = int(quantidade)

            if quantidade < 0:
                raise ValueError

            conexao = conectar()

            conexao.execute(
                """
                UPDATE produtos
                SET estoque = ?
                WHERE id = ?
                """,
                (
                    quantidade,
                    produto_id
                )
            )

            conexao.commit()
            conexao.close()

            return redirect(
                url_for(
                    "estoque",
                    mensagem="Estoque atualizado com sucesso."
                )
            )

        except ValueError:
            pass

    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cantina Fácil - Atualizar Estoque</title>
        <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    </head>
    <body>
        <header class="topbar">
            <div class="logo">Cantina Fácil</div>
            <nav>
                <a href="/dashboard">Dashboard</a>
                <a href="/produtos">Produtos</a>
                <a href="/vendas">Vendas</a>
                <a href="/estoque">Estoque</a>
                <a href="/relatorios">Relatórios</a>
                <a href="/logout">Sair</a>
            </nav>
        </header>

        <main class="container">
            <div class="page-header">
                <div>
                    <h1>Atualizar estoque</h1>
                    <p>{{ produto.nome }}</p>
                </div>
            </div>

            <section class="form-section">
                <form method="POST">
                    <div class="form-group">
                        <label for="quantidade">Quantidade atual</label>
                        <input
                            type="number"
                            id="quantidade"
                            name="quantidade"
                            min="0"
                            value="{{ produto.estoque }}"
                            required
                        >
                    </div>

                    <button type="submit" class="btn-primary">
                        Salvar
                    </button>

                    <a href="/estoque" class="btn-secondary">
                        Cancelar
                    </a>
                </form>
            </section>
        </main>
    </body>
    </html>
    """

    return render_template(
        "estoque_editar.html",
        produto=produto
    ) if False else __import__("flask").render_template_string(
        html,
        produto=produto
    )


@app.route("/relatorios")
@login_obrigatorio
def relatorios():
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    conexao = conectar()

    consulta = """
        SELECT
            v.id,
            v.data,
            v.total,
            v.pagamento,
            COALESCE(SUM(iv.quantidade), 0) AS quantidade_itens
        FROM vendas v
        LEFT JOIN itens_venda iv
            ON iv.venda_id = v.id
    """

    filtros = []
    parametros = []

    if data_inicio:
        filtros.append("DATE(v.data) >= ?")
        parametros.append(data_inicio)

    if data_fim:
        filtros.append("DATE(v.data) <= ?")
        parametros.append(data_fim)

    if filtros:
        consulta += " WHERE " + " AND ".join(filtros)

    consulta += """
        GROUP BY v.id
        ORDER BY v.data DESC
    """

    vendas = conexao.execute(
        consulta,
        parametros
    ).fetchall()

    total_vendas = len(vendas)
    total_vendido = sum(venda["total"] for venda in vendas)

    if total_vendas:
        ticket_medio = total_vendido / total_vendas
    else:
        ticket_medio = 0

    conexao.close()

    return render_template(
        "relatorios.html",
        vendas=vendas,
        total_vendas=total_vendas,
        total_vendido=total_vendido,
        ticket_medio=ticket_medio,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


@app.route("/api/produtos")
@login_obrigatorio
def api_produtos():
    conexao = conectar()

    produtos = conexao.execute(
        """
        SELECT id, nome, categoria, preco, estoque
        FROM produtos
        WHERE ativo = 1
        ORDER BY nome
        """
    ).fetchall()

    conexao.close()

    return jsonify([
        {
            "id": produto["id"],
            "nome": produto["nome"],
            "categoria": produto["categoria"],
            "preco": produto["preco"],
            "estoque": produto["estoque"]
        }
        for produto in produtos
    ])


if __name__ == "__main__":
    inicializar_banco()
    app.run(debug=True)
