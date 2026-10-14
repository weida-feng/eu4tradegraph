"""Streamlit entry point: streamlit run app.py."""

from pathlib import Path

from graphviz.backend import CalledProcessError, ExecutableNotFound
import streamlit as st

from eu4tradegraph import SaveError, parse_save
from eu4tradegraph.export import node_rows, route_rows, to_csv
from eu4tradegraph.render import GraphSettings, default_font, gradient, render_graph

DEMO_PATH = Path(__file__).parent / "examples" / "trade_snapshot_1.34.4.eu4"


@st.cache_data(max_entries=4, show_spinner=False)
def load_snapshot(data: bytes):
    return parse_save(data)


def main():
    st.set_page_config(page_title="EU4 Trade Graph", page_icon="↗", layout="wide")
    st.title("EU4 贸易网络图")
    st.caption("从欧陆风云 IV 存档查看贸易节点、流向与贸易值")
    st.info("支持范围：EU4 1.34.x · 无 Mod · 非压缩文本存档。参考样本为 1.34.4；1.34 以外的版本尚未验证，上传时会被拒绝。")
    source = st.radio("数据来源", ("内置演示", "上传存档"), horizontal=True)
    if source == "内置演示":
        data = DEMO_PATH.read_bytes()
        st.caption("演示数据来自原项目 1.34.4.0 存档，仅保留贸易字段；它不能在游戏中加载。")
    else:
        uploaded = st.file_uploader("上传 .eu4 非压缩文本存档（最大 200 MB）", type=["eu4"])
        if uploaded is None:
            st.caption("在游戏保存界面关闭压缩。压缩、二进制和铁人存档不在支持范围内。")
            return
        data = uploaded.getvalue()
    try:
        with st.spinner("读取贸易数据…"):
            snapshot = load_snapshot(data)
    except SaveError as error:
        st.error(str(error))
        return
    columns = st.columns(3)
    columns[0].metric("存档版本 / 日期", f"{snapshot.version} / {snapshot.date}")
    columns[1].metric("贸易节点", len(snapshot.nodes))
    columns[2].metric("贸易路线", len(snapshot.routes))

    with st.form("graph_settings"):
        with st.expander("调整图形", expanded=False):
            left, right = st.columns(2)
            with left:
                aspect = st.slider("图片宽高比（宽度 / 高度）", 0.5, 4.0, 2.16)
                edge = st.slider("线宽范围（贸易流量）", 0.5, 12.0, (1.0, 6.0))
                size = st.slider("节点尺寸范围（当前贸易值）", 0.3, 6.0, (0.6, 1.8))
                font_size = st.slider("字号范围", 8.0, 48.0, (12.0, 22.0))
            with right:
                chinese = st.checkbox("使用中文节点名", value=True)
                font = st.text_input("字体（需在运行环境中安装）", value=default_font())
                st.caption("颜色表示本地贸易产出；色相沿 HSV 渐变插值。")
                start = tuple(st.slider(f"低值颜色 · {name}", 0.0, 1.0, value, key=f"start_{name}")
                              for name, value in zip(("H", "S", "V"), (0.0, 0.5, 1.0)))
                end = tuple(st.slider(f"高值颜色 · {name}", 0.0, 1.0, value, key=f"end_{name}")
                            for name, value in zip(("H", "S", "V"), (2 / 3, 0.5, 1.0)))
        submitted = st.form_submit_button("生成贸易网络图", type="primary")

    settings = GraphSettings(aspect, edge, size, font_size, start, end, font, chinese)
    # Persist only this session's latest output; each source/settings pair owns it.
    render_key = (snapshot, settings)
    if submitted:
        try:
            with st.spinner("生成网络图…"):
                png = render_graph(snapshot, settings, "png")
                svg = render_graph(snapshot, settings, "svg")
            st.session_state["rendered"] = (render_key, png, svg)
        except ExecutableNotFound:
            st.error("未找到 Graphviz。请安装系统 Graphviz 并将 dot 加入 PATH，安装步骤见 README。")
        except (CalledProcessError, OSError):
            st.error("图形生成失败，请检查 Graphviz 安装和字体设置，或缩小图形尺寸。")

    graph_tab, nodes_tab, routes_tab = st.tabs(("贸易网络", "节点数据", "路线数据"))
    with graph_tab:
        rendered = st.session_state.get("rendered")
        if rendered and rendered[0] == render_key:
            st.image(rendered[1], caption="节点内数字为 current 当前贸易值", width="stretch")
            first, second = st.columns(2)
            first.download_button("下载 PNG", rendered[1], "eu4_trade.png", "image/png")
            second.download_button("下载 SVG", rendered[2], "eu4_trade.svg", "image/svg+xml")
        else:
            st.caption("点击“生成贸易网络图”查看当前数据与设置的结果。")
        st.image(gradient(settings), caption="本地贸易产出：低 → 高", width=640)
        st.caption("节点大小与数字：current · 线宽：路线 value · 虚线：零流量 · 方框：内陆节点 · 椭圆：沿海节点")
        st.caption("贸易值来自存档，不等同于某个国家的贸易收入；图形为节点关系图，不表示地理距离。")
    with nodes_tab:
        rows = node_rows(snapshot)
        st.dataframe(sorted(rows, key=lambda row: row["current"], reverse=True), hide_index=True, width="stretch")
        st.download_button("下载节点 CSV", to_csv(rows, ("node_id", "label_zh", "inland", "current", "local_value", "outgoing")),
                           "eu4_trade_nodes.csv", "text/csv")
    with routes_tab:
        rows = route_rows(snapshot)
        st.dataframe(sorted(rows, key=lambda row: row["value"], reverse=True), hide_index=True, width="stretch")
        st.download_button("下载路线 CSV", to_csv(rows, ("source", "target", "value")),
                           "eu4_trade_routes.csv", "text/csv")


if __name__ == "__main__":
    main()
