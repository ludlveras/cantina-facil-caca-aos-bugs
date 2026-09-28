function adicionarItem() {
    const container = document.getElementById("itensVenda");

    const primeiroItem = container.querySelector(".item-venda");

    if (!primeiroItem) {
        return;
    }

    const novoItem = primeiroItem.cloneNode(true);

    novoItem.querySelector("select").value = "";
    novoItem.querySelector("input").value = "1";

    container.appendChild(novoItem);

    atualizarTotal();
}

function calcularTotal() {
    const itens = document.querySelectorAll(".item-venda");

    let total = 0;

    itens.forEach(item => {
        const select = item.querySelector("select");
        const quantidade = item.querySelector("input");

        if (!select || !quantidade) {
            return;
        }

        const opcao = select.options[select.selectedIndex];

        if (!opcao || !opcao.dataset.preco) {
            return;
        }

        const preco = parseFloat(opcao.dataset.preco);
        const qtd = parseInt(quantidade.value);

        if (!isNaN(preco) && !isNaN(qtd)) {
            total += preco * qtd;
        }
    });

    return total;
}

function atualizarTotal() {
    const elemento = document.getElementById("totalVenda");

    if (!elemento) {
        return;
    }

    const total = calcularTotal();

    elemento.textContent = total.toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL"
    });
}

document.addEventListener("change", function(event) {
    if (
        event.target.matches("#itensVenda select") ||
        event.target.matches("#itensVenda input")
    ) {
        atualizarTotal();
    }
});

document.addEventListener("input", function(event) {
    if (event.target.matches("#itensVenda input")) {
        atualizarTotal();
    }
});

document.addEventListener("DOMContentLoaded", function() {
    atualizarTotal();
});