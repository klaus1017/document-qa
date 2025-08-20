# =============================================================================
# UI渲染和主要功能函数
# =============================================================================

def render_analysis_results(df):
    """渲染分析结果 - 主要入口函数"""
    if df.empty:
        st.warning("没有数据可供分析")
        return
    
    # 计算汇总数据和变差分析
    monthly_material_summary, monthly_dept_summary = calculate_monthly_summary(df)
    variance_analysis = calculate_comprehensive_variance_analysis(df)
    
    # 显示关键指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_cost = df['TOTAL_COST'].sum()
        st.metric("总成本", f"¥{total_cost/10000:.2f}万")
    
    with col2:
        total_quan = df['QUAN'].sum()
        st.metric("总数量", f"{total_quan:,.0f}")
    
    with col3:
        # 由于产出是部门级别的，需要去重计算
        total_wpnl = df.groupby(['DEPT_NAME_STD', 'YYYYMM'])['WPNL_SIZE'].first().sum()
        st.metric("总产出", f"{total_wpnl/10000:.2f}万")
    
    with col4:
        # 计算总体平均单耗
        total_unit_consumption = total_cost / total_wpnl if total_wpnl > 0 else 0
        st.metric("总体平均单耗", f"¥{total_unit_consumption:.2f}")
    
    # 创建标签页
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["数量分析", "部门分析", "物料分析", "单价分析", "月度趋势","AI分析"])
    
    # 渲染各个标签页
    render_quantity_analysis_tab(tab1, variance_analysis)
    render_department_analysis_tab(tab2, variance_analysis)
    render_material_analysis_tab(tab3, monthly_dept_summary)
    render_price_analysis_tab(tab4, monthly_material_summary, df)
    render_trend_analysis_tab(tab5, df)
    render_ai_analysis_tab(tab6, df)

def render_quantity_analysis_tab(tab, variance_analysis):
    """渲染数量分析标签页"""
    with tab:
        st.subheader("数量分析 - 每个物料的每日领用量")
        
        # 显示变差最大物料的数量趋势图
        if '数量变差' in variance_analysis and not variance_analysis['数量变差'].empty:
            # 获取变差最大的前10个物料
            top_variance_materials = variance_analysis['数量变差']['INV'].tolist()
            
            if '每日数量数据' in variance_analysis:
                # 筛选变差最大的物料数据用于绘图
                plot_data = variance_analysis['每日数量数据'][
                    variance_analysis['每日数量数据']['INV'].isin(top_variance_materials)
                ]
                
                if not plot_data.empty:
                    # 绘制变差最大物料的每日数量趋势
                    fig_qty_trend = px.line(
                        plot_data,
                        x='DATE',
                        y='QUAN',
                        color='INV',
                        title='数量变差最大的前10个物料每日领用量趋势',
                        labels={'QUAN': '领用量', 'DATE': '日期', 'INV': '物料'}
                    )
                    fig_qty_trend.update_layout(height=500)
                    st.plotly_chart(fig_qty_trend, use_container_width=True)
        
        # 每日耗用量变差前10名明细
        st.subheader("每日耗用量变差前10名明细（较前一天）")
        
        if '数量变差' in variance_analysis and not variance_analysis['数量变差'].empty:
            qty_variance_display = variance_analysis['数量变差'][
                ['INV', 'DATE', 'QUAN', '前一天数量', '数量变差', '数量变差百分比']
            ].copy()
            qty_variance_display.columns = ['物料', '当前日期', '当日数量', '前一天数量', '数量变差', '变差百分比(%)']
            
            # 处理边界情况：当前一天数量为0时显示特殊标记
            qty_variance_display['变差百分比(%)'] = qty_variance_display['变差百分比(%)'].fillna('∞')
            
            try:
                st.dataframe(
                    qty_variance_display.style.format({
                        '当日数量': '{:,.0f}',
                        '前一天数量': '{:,.0f}',
                        '数量变差': '{:+,.0f}',
                        '变差百分比(%)': lambda x: f'{x:+.2f}%' if isinstance(x, (int, float)) else str(x)
                    }),
                    use_container_width=True
                )
            except:
                st.dataframe(qty_variance_display, use_container_width=True)
        else:
            st.info("没有足够的数据进行每日耗用量变差分析")
        
        # 月度耗用量变差前10名明细
        st.subheader("月度耗用量变差前10名明细（较上月）")
        
        if '月数量变差' in variance_analysis and not variance_analysis['月数量变差'].empty:
            monthly_qty_variance_display = variance_analysis['月数量变差'][
                ['INV', '年月', 'QUAN', '上月数量', '月数量变差', '月数量变差百分比']
            ].copy()
            monthly_qty_variance_display.columns = ['物料', '当前月份', '当月数量', '上月数量', '数量变差', '变差百分比(%)']
            
            # 处理边界情况
            monthly_qty_variance_display['变差百分比(%)'] = monthly_qty_variance_display['变差百分比(%)'].fillna('∞')
            
            try:
                st.dataframe(
                    monthly_qty_variance_display.style.format({
                        '当月数量': '{:,.0f}',
                        '上月数量': '{:,.0f}',
                        '数量变差': '{:+,.0f}',
                        '变差百分比(%)': lambda x: f'{x:+.2f}%' if isinstance(x, (int, float)) else str(x)
                    }),
                    use_container_width=True
                )
            except:
                st.dataframe(monthly_qty_variance_display, use_container_width=True)
        else:
            st.info("没有足够的数据进行月度耗用量变差分析")

def render_department_analysis_tab(tab, variance_analysis):
    """渲染部门分析标签页"""
    with tab:
        st.subheader("部门分析 - 单耗排名")
        
        # 部门单耗排名
        if '日单耗数据' in variance_analysis:
            # 计算各部门内物料的平均单耗排名
            dept_material_unit_consumption = variance_analysis['日单耗数据'].groupby(['DEPT_NAME_STD', 'INV']).agg({
                '日单耗': 'mean',
                'TOTAL_COST': 'sum'
            }).reset_index()
            
            # 选择部门进行分析
            dept_list = dept_material_unit_consumption['DEPT_NAME_STD'].unique()
            selected_dept = st.selectbox("选择部门查看单耗排名：", dept_list)
            
            if selected_dept:
                dept_data = dept_material_unit_consumption[
                    dept_material_unit_consumption['DEPT_NAME_STD'] == selected_dept
                ].sort_values('日单耗', ascending=False)
                
                st.subheader(f"{selected_dept} - 物料单耗排名")
                
                # 显示排名表
                dept_ranking_display = dept_data[['INV', '日单耗', 'TOTAL_COST']].copy()
                dept_ranking_display['总成本'] = dept_ranking_display['TOTAL_COST'] / 10000  # 转换为万元
                dept_ranking_display.columns = ['物料', '平均日单耗', '总成本']
                dept_ranking_display['排名'] = range(1, len(dept_ranking_display) + 1)
                dept_ranking_display = dept_ranking_display[['排名', '物料', '平均日单耗', '总成本']]
                
                try:
                    st.dataframe(
                        dept_ranking_display.style.format({
                            '平均日单耗': '¥{:.2f}',
                            '总成本': '¥{:.2f}万'
                        }),
                        use_container_width=True
                    )
                except:
                    st.dataframe(dept_ranking_display, use_container_width=True)
                
                # 显示该部门的单耗变差
                if '单耗变差' in variance_analysis:
                    dept_unit_variance = variance_analysis['单耗变差'][
                        variance_analysis['单耗变差']['DEPT_NAME_STD'] == selected_dept
                    ]
                    
                    if not dept_unit_variance.empty:
                        st.subheader(f"{selected_dept} - 单耗变差前10名明细（较上月）")
                        
                        dept_variance_display = dept_unit_variance[
                            ['INV', '年月', '月单耗', '上月单耗', '单耗变差', '单耗变差百分比']
                        ].copy()
                        dept_variance_display.columns = ['物料', '当前月份', '本月单耗', '上月单耗', '单耗变差', '变差百分比(%)']
                        
                        # 处理边界情况
                        dept_variance_display['变差百分比(%)'] = dept_variance_display['变差百分比(%)'].fillna('∞')
                        
                        try:
                            st.dataframe(
                                dept_variance_display.style.format({
                                    '本月单耗': '¥{:.2f}',
                                    '上月单耗': '¥{:.2f}',
                                    '单耗变差': '¥{:+.2f}',
                                    '变差百分比(%)': lambda x: f'{x:+.2f}%' if isinstance(x, (int, float)) else str(x)
                                }),
                                use_container_width=True
                            )
                        except:
                            st.dataframe(dept_variance_display, use_container_width=True)
                    else:
                        st.info(f"{selected_dept} 暂无单耗变差数据")
        else:
            st.info("没有足够的数据进行部门单耗排名分析")

def render_material_analysis_tab(tab, monthly_dept_summary):
    """渲染物料分析标签页"""
    with tab:
        st.subheader("部门成本分析")
        
        if not monthly_dept_summary.empty:
            # 部门成本排名
            dept_ranking = monthly_dept_summary.groupby(['DEPT_CODE_STD', 'DEPT_NAME_STD']).agg({
                'TOTAL_COST': 'sum',
                'WPNL_SIZE': 'sum',
                'INV': 'sum'  # 物料种类总数
            }).reset_index().sort_values('TOTAL_COST', ascending=False)
            
            # 计算部门单耗
            dept_ranking['UNIT_CONSUMPTION'] = dept_ranking['TOTAL_COST'] / dept_ranking['WPNL_SIZE']
            dept_ranking['UNIT_CONSUMPTION'] = dept_ranking['UNIT_CONSUMPTION'].fillna(0)
            
            # 添加单耗排名
            dept_unit_ranking = dept_ranking.sort_values('UNIT_CONSUMPTION', ascending=False)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 部门成本排名图
                fig_cost = px.bar(dept_ranking.head(10), 
                       x='DEPT_NAME_STD', 
                       y='TOTAL_COST',
                       title="部门成本排名 (前10名)")
                fig_cost.update_xaxes(tickangle=45)
                st.plotly_chart(fig_cost, use_container_width=True)
            
            with col2:
                # 部门单耗排名图
                fig_unit = px.bar(dept_unit_ranking.head(10), 
                           x='DEPT_NAME_STD', 
                           y='UNIT_CONSUMPTION',
                           title="部门单耗排名 (前10名)",
                           color='UNIT_CONSUMPTION',
                           color_continuous_scale='Reds')
                fig_unit.update_xaxes(tickangle=45)
                st.plotly_chart(fig_unit, use_container_width=True)
            
            # 部门详细表格
            st.subheader("部门汇总数据")
            
            # 检查必要的列是否存在
            required_cols = ['DEPT_NAME_STD', 'TOTAL_COST', 'WPNL_SIZE', 'INV', 'UNIT_CONSUMPTION']
            if all(col in dept_ranking.columns for col in required_cols):
                display_dept_df = dept_ranking[required_cols].copy()
                display_dept_df['TOTAL_COST'] = display_dept_df['TOTAL_COST'] / 10000  # 转换为万元
                display_dept_df['WPNL_SIZE'] = display_dept_df['WPNL_SIZE'] / 10000  # 转换为万
                display_dept_df.columns = ['部门名称', '总成本', '产出', '物料种类数', '部门单耗']
            else:
                st.error(f"数据结构异常，缺少必要的列。现有列：{list(dept_ranking.columns)}")
                display_dept_df = pd.DataFrame()
            
            try:
                st.dataframe(
                    display_dept_df.style.format({
                        '总成本': '¥{:.2f}万',
                        '产出': '{:.2f}万',
                        '物料种类数': '{:,.0f}',
                        '部门单耗': '¥{:.2f}'
                    }),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(display_dept_df, use_container_width=True)
                
            # 单耗排名表
            st.subheader("部门单耗排名")
            required_ranking_cols = ['DEPT_NAME_STD', 'UNIT_CONSUMPTION', 'TOTAL_COST', 'WPNL_SIZE']
            if all(col in dept_unit_ranking.columns for col in required_ranking_cols):
                display_unit_ranking_df = dept_unit_ranking[required_ranking_cols].copy()
                display_unit_ranking_df['TOTAL_COST'] = display_unit_ranking_df['TOTAL_COST'] / 10000  # 转换为万元
                display_unit_ranking_df['WPNL_SIZE'] = display_unit_ranking_df['WPNL_SIZE'] / 10000  # 转换为万
                display_unit_ranking_df.columns = ['部门名称', '单耗', '总成本', '产出']
                display_unit_ranking_df['排名'] = range(1, len(display_unit_ranking_df) + 1)
                display_unit_ranking_df = display_unit_ranking_df[['排名', '部门名称', '单耗', '总成本', '产出']]
            else:
                st.error(f"单耗排名数据结构异常，缺少必要的列。现有列：{list(dept_unit_ranking.columns)}")
                display_unit_ranking_df = pd.DataFrame()
            
            try:
                st.dataframe(
                    display_unit_ranking_df.style.format({
                        '单耗': '¥{:.2f}',
                        '总成本': '¥{:.2f}万',
                        '产出': '{:.2f}万'
                    }),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(display_unit_ranking_df, use_container_width=True)

def render_price_analysis_tab(tab, monthly_material_summary, df):
    """渲染单价分析标签页"""
    with tab:
        st.subheader("单价分析")
        
        if not monthly_material_summary.empty:
            # 按部门分组进行物料分析
            departments = monthly_material_summary['DEPT_NAME_STD'].unique()
            
            # 部门选择器
            selected_dept_analysis = st.selectbox(
                "选择部门进行物料单耗分析",
                options=['全部部门'] + list(departments),
                key='dept_material_analysis'
            )

            if selected_dept_analysis == '全部部门':
                # 显示所有部门的物料成本排名
                inv_ranking = (
                    monthly_material_summary.groupby(
                        ['INV', 'INV_PART_DESCRIPTION', 'DEPT_CODE_STD', 'DEPT_NAME_STD']
                    )
                    .agg({
                        'TOTAL_COST': 'sum',
                        'QUAN': 'sum',
                        'WPNL_SIZE': 'first',  # 产出
                        'UNIT_CONSUMPTION': 'mean'  # 平均单耗
                    })
                    .reset_index()
                    .sort_values('TOTAL_COST', ascending=False)
                )

                fig = px.bar(
                    inv_ranking.head(15),
                    x='INV_PART_DESCRIPTION',
                    y='TOTAL_COST',
                    color='DEPT_NAME_STD',
                    title="物料成本排名 (前15名)"
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

                # 物料详细表格
                st.subheader("物料汇总数据")
                required_inv_cols = [
                    'INV_PART_DESCRIPTION', 'DEPT_NAME_STD', 'TOTAL_COST', 'QUAN', 'WPNL_SIZE', 'UNIT_CONSUMPTION'
                ]
                if all(col in inv_ranking.columns for col in required_inv_cols):
                    display_inv_df = inv_ranking[required_inv_cols].copy()
                    display_inv_df['TOTAL_COST'] = display_inv_df['TOTAL_COST'] / 10000  # 转换为万元
                    display_inv_df['WPNL_SIZE'] = display_inv_df['WPNL_SIZE'] / 10000  # 转换为万
                    display_inv_df.columns = ['物料描述', '所属部门', '总成本', '总数量', '产出', '单耗']
                else:
                    st.error(
                        f"物料数据结构异常，缺少必要的列。现有列：{list(inv_ranking.columns)}"
                    )
                    display_inv_df = pd.DataFrame()

                try:
                    st.dataframe(
                        display_inv_df.style.format({
                            '总成本': '¥{:.2f}万',
                            '总数量': '{:,.0f}',
                            '产出': '{:.2f}万',
                            '单耗': '¥{:.2f}'
                        }),
                        use_container_width=True
                    )
                except Exception:
                    st.dataframe(display_inv_df, use_container_width=True)
            else:
                # 分析特定部门的物料单耗趋势
                dept_materials = monthly_material_summary[
                    monthly_material_summary['DEPT_NAME_STD'] == selected_dept_analysis
                ].copy()

                if not dept_materials.empty:
                    st.subheader(f"{selected_dept_analysis} - 物料单耗趋势分析")
                    
                    # 按物料和年月分析单耗趋势
                    material_trend = dept_materials.groupby(['INV', 'YEAR_MONTH']).agg({
                        'UNIT_CONSUMPTION': 'mean',
                        'TOTAL_COST': 'sum',
                        'QUAN': 'sum'
                    }).reset_index()
            
                    # 获取单耗最高的前10个物料
                    top_materials_unit = dept_materials.groupby('INV')['UNIT_CONSUMPTION'].mean().nlargest(10)
                    top_material_trend = material_trend[material_trend['INV'].isin(top_materials_unit.index)]
                    
                    if not top_material_trend.empty:
                        # 转换年月为字符串
                        top_material_trend['年月字符串'] = top_material_trend['YEAR_MONTH'].astype(str)
                        
                        # 绘制单耗趋势图
                        fig_unit_trend = px.line(
                            top_material_trend,
                            x='年月字符串',
                            y='UNIT_CONSUMPTION',
                            color='INV',
                            title=f'{selected_dept_analysis} - 前10大单耗物料趋势',
                            labels={'UNIT_CONSUMPTION': '单耗 (¥)', '年月字符串': '年月', 'INV': '物料'}
                        )
                        fig_unit_trend.update_layout(height=500)
                        st.plotly_chart(fig_unit_trend, use_container_width=True)
                    else:
                        st.info("该部门没有物料单耗趋势数据")
                else:
                    st.info("该部门没有物料数据")

def render_trend_analysis_tab(tab, df):
    """渲染月度趋势分析标签页"""
    with tab:
        st.subheader("单价变差分析")

        # 获取日期范围用于单价趋势查询
        if 'DATE' in df.columns:
            start_date = df['DATE'].min()
            end_date = df['DATE'].max()
        else:
            start_date = pd.to_datetime(df['YYYYMM'].min() + '01', format='%Y%m%d')
            end_date = pd.to_datetime(df['YYYYMM'].max() + '01', format='%Y%m%d') + pd.offsets.MonthEnd(0)

        # 加载所有料号的单价数据
        unit_price_df = load_unit_price_data(start_date, end_date)

        if not unit_price_df.empty:
            # 每日单价变差分析（跟前一天对比）
            st.subheader("每日单价变差前10名明细")
            
            # 计算每日单价变化（跟前一天对比）
            unit_price_daily = unit_price_df.sort_values(['INV', 'DATE'])
            unit_price_daily['前一天单价'] = unit_price_daily.groupby('INV')['UNIT_PRICE'].shift(1)
            unit_price_daily['日单价变差'] = unit_price_daily['UNIT_PRICE'] - unit_price_daily['前一天单价']
            unit_price_daily['日单价变差百分比'] = (unit_price_daily['日单价变差'] / unit_price_daily['前一天单价'] * 100).round(2)
            
            # 筛选最新日期的数据并按变差绝对值排序
            latest_date = unit_price_daily['DATE'].max()
            current_day_price_changes = unit_price_daily[
                (unit_price_daily['DATE'] == latest_date) & 
                (unit_price_daily['日单价变差百分比'].notna())
            ].copy()
            
            current_day_price_changes['单价变差绝对值'] = current_day_price_changes['日单价变差百分比'].abs()
            top_daily_price_changes = current_day_price_changes.nlargest(10, '单价变差绝对值')
            
            if not top_daily_price_changes.empty:
                display_daily_price_changes_df = top_daily_price_changes[['INV', 'DATE', '日单价变差百分比']].copy()
                display_daily_price_changes_df.columns = ['物料', '当前日期', '变差百分比(%)']
                
                try:
                    st.dataframe(
                        display_daily_price_changes_df.style.format({
                            '变差百分比(%)': '{:+.2f}%'
                        }),
                        use_container_width=True
                    )
                except Exception:
                    st.dataframe(display_daily_price_changes_df, use_container_width=True)
            else:
                st.info("没有足够的日度数据进行每日单价变差分析")
        else:
            st.warning("无法加载单价数据。")

def render_ai_analysis_tab(tab, df):
    """渲染AI分析标签页"""
    with tab:
        st.subheader("AI智能分析助手")
        st.caption("与AI对话，分析当前单耗数据")
        
        # LLM配置
        llm_model_name = "QWQ:32B" 
        llm_base_url = "http://172.18.80.88:8106/v1"
        
        # 记录数限制配置
        col1, col2 = st.columns([1, 3])
        with col1:
            max_rows = st.number_input(
                "分析最大数据量", 
                min_value=10, 
                max_value=1000,
                value=500,
                step=50,
                key="cost_llm_max_rows"
            )
        
        # 创建消息容器
        message_container = st.container()
        # 显示历史消息
        with message_container:
            for i, message in enumerate(st.session_state.cost_llm_messages):
                if message["role"] == "user":
                    # 用户消息显示在右侧
                    col1, col2 = st.columns([1, 3])
                    with col2:
                        st.markdown(f"""
                        <div style="background-color: #e3f2fd; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                            <strong>用户:</strong><br>
                            {message["content"]}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    # LLM消息显示在左侧
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"""
                        <div style="background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                            <strong>AI助手:</strong><br>
                            {message["content"]}
                        </div>
                        """, unsafe_allow_html=True)
        
        # 使用streamlit的chat_input作为输入框
        user_input = st.chat_input("请分析当前单耗数据")
        
        # 处理用户输入
        if user_input:
            # 添加用户消息到会话状态
            st.session_state.cost_llm_messages.append({"role": "user", "content": user_input})
            
            # 显示用户消息
            with message_container:
                col1, col2 = st.columns([1, 3])
                with col2:
                    st.markdown(f"""
                    <div style="background-color: #e3f2fd; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                        <strong>用户:</strong><br>
                        {user_input}
                    </div>
                    """, unsafe_allow_html=True)
            
            # 显示助手消息
            with message_container:
                col1, col2 = st.columns([3, 1])
                with col1:
                    # 创建一个占位符用于流式输出
                    message_placeholder = st.empty()
                    message_placeholder.markdown("""
                    <div style="background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                        <strong>AI助手:</strong><br>
                        正在分析中...
                    </div>
                    """, unsafe_allow_html=True)

                    try:
                        # 创建一个专用于LLM的数据副本
                        llm_df = df.copy()
                        
                        # 需要删除的列列表（分析生成的技术字段）
                        columns_to_remove = [
                            'IS_ANOMALY',
                            'Predicted', 
                            'Lower', 
                            'Upper', 
                            'Actual'
                        ]

                        # 从DataFrame中删除存在的列
                        for col in columns_to_remove:
                            if col in llm_df.columns:
                                llm_df.drop(col, axis=1, inplace=True)
                        
                        # 处理DATE列的格式转换和排序
                        if 'DATE' in llm_df.columns:
                            try:
                                # 确保DATE是datetime类型用于排序
                                llm_df['DATE'] = pd.to_datetime(llm_df['DATE'])
                                # 按时间从新到旧排序
                                llm_df = llm_df.sort_values('DATE', ascending=False)
                                # 限制为最新的max_rows条记录
                                llm_df_final = llm_df.head(max_rows)
                                # 将DATE转为字符串格式用于JSON序列化
                                llm_df_final['DATE'] = llm_df_final['DATE'].dt.strftime('%Y-%m-%d')
                            except Exception as date_err:
                                st.warning(f"处理DATE列时出错: {date_err}. 将使用未排序的数据。")
                                llm_df_final = llm_df.head(max_rows)
                        else:
                            # 按YYYYMM排序
                            try:
                                llm_df = llm_df.sort_values('YYYYMM', ascending=False)
                                llm_df_final = llm_df.head(max_rows)
                            except:
                                llm_df_final = llm_df.head(max_rows)
                        
                        # 将精简后的数据集转换为CSV格式
                        data_context = llm_df_final.to_csv(index=False)
                        
                        # 调用LLM
                        try:
                            system_prompt = """你是一个专业的成本分析师和数据分析助手。请基于提供的单耗分析数据和用户问题进行深入分析并回答。

                                数据字段说明：
                                - YYYYMM: 年月
                                - DEPT_NAME_STD: 部门名称
                                - INV: 物料品名
                                - INV_PART_DESCRIPTION: 物料描述
                                - QUAN: 数量
                                - STD_COST: 单价
                                - TOTAL_COST: 总成本
                                - WPNL_SIZE: 产出
                                - UNIT_CONSUMPTION: 单耗（总成本/产出）
                                - YEAR_MONTH: 年月期间
                                - DEPT_CODE_STD: 部门代码

                                请根据数据特点提供专业的成本分析建议。"""
                            
                            data_description = f"单耗分析数据：最新的{len(llm_df_final)}条记录\n数据时间范围：{llm_df_final.get('YYYYMM', pd.Series()).min() or '未知'} 至 {llm_df_final.get('YYYYMM', pd.Series()).max() or '未知'}\n\n"
                            
                            llm = ChatOpenAI(
                                model=llm_model_name,
                                openai_api_key="dummy-key",
                                openai_api_base=llm_base_url,
                                temperature=0,
                                streaming=True  # 启用流式输出
                            )
                            
                            enhanced_prompt = f"""
                                {data_description}以下是CSV格式的单耗分析数据：
                                ```csv
                                {data_context}
                                ```

                                用户问题: {user_input}

                                请根据以上单耗分析数据进行专业分析并回答。
                                """
                            
                            messages = [
                                SystemMessage(content=system_prompt),
                                HumanMessage(content=enhanced_prompt)
                            ]
                            
                            # 使用流式输出
                            llm_response_content = ""
                            for chunk in llm.stream(messages):
                                if chunk.content:
                                    llm_response_content += chunk.content
                                    message_placeholder.markdown(f"""
                                    <div style="background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                                        <strong>AI助手:</strong><br>
                                        {llm_response_content}▌
                                    </div>
                                    """, unsafe_allow_html=True)
                            
                            # 移除光标并显示最终内容
                            message_placeholder.markdown(f"""
                            <div style="background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                                <strong>AI助手:</strong><br>
                                {llm_response_content}
                            </div>
                            """, unsafe_allow_html=True)
                            
                        except Exception as llm_err:
                            llm_response_content = f"调用本地 LLM (模型: {llm_model_name} @ {llm_base_url}) 时出错: {llm_err}"
                            st.error(llm_response_content)
                            message_placeholder.markdown(f"""
                            <div style="background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                                <strong>AI助手:</strong><br>
                                {llm_response_content}
                            </div>
                            """, unsafe_allow_html=True)

                    except Exception as e:
                        error_msg = f"处理数据时出错: {e}"
                        message_placeholder.markdown(f"""
                        <div style="background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: left;">
                            <strong>AI助手:</strong><br>
                            {error_msg}
                        </div>
                        """, unsafe_allow_html=True)
                        llm_response_content = error_msg
                    
                    # 添加助手消息到会话状态
                    st.session_state.cost_llm_messages.append({"role": "assistant", "content": llm_response_content})

def render_sidebar_filters():
    """渲染侧边栏筛选器"""
    with st.sidebar:
        # 数据库连接状态
        with st.status("连接数据库...", expanded=False) as status:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM DUAL")
                    cursor.fetchone()
                status.update(label="已连接数据库", state="complete", expanded=False)
            except Exception as e:
                status.update(label=f"数据库连接失败: {e}", state="error", expanded=True)
                st.stop()
        
        st.markdown("---")
        
        # 设置默认时间为最近三个月
        today = date.today()
        default_start = today - timedelta(days=90)  # 三个月前
        default_end = today
        
        # 日期输入控件
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "开始日期", 
                value=default_start
            )
        with col_end:
            end_date = st.date_input(
                "结束日期", 
                value=default_end
            )
         
        # 根据时间范围自动加载筛选选项
        with st.spinner("正在加载筛选选项..."):
            try:
                dept_options, inv_options = load_filter_options(start_date, end_date)
            except Exception as e:
                st.error(f"加载筛选选项失败: {e}")
                dept_options, inv_options = pd.DataFrame(), pd.DataFrame()
        
        # 初始化筛选选项
        selected_dept = "全部"
        selected_inv = "全部"
        
        if not dept_options.empty:
            # 部门筛选
            dept_list = ["全部"] + dept_options['DEPT_CODE_STD'].tolist()
            dept_format_func = lambda x: "全部" if x == "全部" else dept_options[dept_options['DEPT_CODE_STD']==x]['DEPT_NAME_STD'].iloc[0]
            
            selected_dept = st.selectbox(
                "部门选择",
                options=dept_list,
                format_func=dept_format_func,
                help=f"当前时间范围内共有 {len(dept_options)} 个部门"
            )
            
            # 根据选择的部门获取物料选项
            if selected_dept != "全部":
                try:
                    # 加载选定部门下的物料选项
                    with get_db_connection() as conn:
                        query = """
                        SELECT DISTINCT 品名 as INV
                        FROM VI_Wlcb_cost_ai
                        WHERE YYYYMM >= TO_CHAR(:start_date, 'YYYYMM')
                          AND YYYYMM <= TO_CHAR(:end_date, 'YYYYMM')
                          AND 部門名稱 = :dept
                        ORDER BY 品名
                        """
                        df_materials = pd.read_sql(query, conn, params={
                            'start_date': start_date,
                            'end_date': end_date,
                            'dept': selected_dept
                        })
                        if not df_materials.empty:
                            df_materials['INV_PART_DESCRIPTION'] = df_materials['INV']  # 使用品名作为显示名称
                            filtered_inv_options = df_materials
                        else:
                            filtered_inv_options = pd.DataFrame()
                except Exception as e:
                    st.warning(f"加载物料选项失败: {e}")
                    filtered_inv_options = inv_options
            else:
                filtered_inv_options = inv_options
            
            # 物料筛选
            if not filtered_inv_options.empty:
                inv_list = ["全部"] + filtered_inv_options['INV'].tolist()
                inv_format_func = lambda x: "全部" if x == "全部" else filtered_inv_options[filtered_inv_options['INV']==x]['INV_PART_DESCRIPTION'].iloc[0]
                
                material_help_text = f"当前部门下共有 {len(filtered_inv_options)} 个物料" if selected_dept != "全部" else f"所有部门下共有 {len(filtered_inv_options)} 个物料"
                selected_inv = st.selectbox(
                    "物料选择",
                    options=inv_list,
                    format_func=inv_format_func,
                    help=material_help_text
                )
            else:
                st.selectbox("物料选择", ["指定条件下无数据"], disabled=True)
        else:
            # 没有筛选选项时显示提示
            st.selectbox("部门选择", ["指定时间范围内无数据"], disabled=True)
            st.selectbox("物料选择", ["指定时间范围内无数据"], disabled=True)
            st.warning("指定时间范围内没有数据，请调整时间范围")
        
        # 按钮区域
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            # 加载数据按钮
            load_data = st.button("加载数据", use_container_width=True, type="primary", disabled=dept_options.empty)
        
        with col_btn2:
            # 重置筛选按钮
            if st.button("重置筛选", use_container_width=True):
                st.session_state.reset_filters = True
                st.rerun()
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'load_data': load_data,
            'selected_dept': selected_dept,
            'selected_inv': selected_inv,
            'dept_options': dept_options,
            'inv_options': inv_options
        }

def render_quantity_trend_analysis(df: pd.DataFrame):
    """渲染数量趋势分析"""
    if df.empty:
        st.warning("数量趋势数据为空")
        return
    
    # 数量趋势图
    fig = px.line(df, x='DATE', y='TOTAL_QUAN', 
                  title='总数量趋势', 
                  labels={'TOTAL_QUAN': '总数量', 'DATE': '日期'})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # 显示统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("最大日数量", f"{df['TOTAL_QUAN'].max():,.0f}")
    with col2:
        st.metric("平均日数量", f"{df['TOTAL_QUAN'].mean():,.0f}")
    with col3:
        st.metric("总数量", f"{df['TOTAL_QUAN'].sum():,.0f}")

def render_unit_price_analysis(df: pd.DataFrame):
    """渲染单价分析"""
    if df.empty:
        st.warning("单价数据为空")
        return
    
    # 选择料号进行分析
    materials = df['INV'].unique()
    if len(materials) > 0:
        selected_material = st.selectbox("选择物料查看单价趋势", materials)
        
        material_data = df[df['INV'] == selected_material]
        if not material_data.empty:
            # 单价趋势图
            fig = px.line(material_data, x='DATE', y='UNIT_PRICE',
                         title=f'{selected_material} 单价趋势',
                         labels={'UNIT_PRICE': '单价 (¥)', 'DATE': '日期'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # 计算价格变化
            material_data = material_data.sort_values('DATE')
            if len(material_data) >= 2:
                first_price = material_data.iloc[0]['UNIT_PRICE']
                last_price = material_data.iloc[-1]['UNIT_PRICE']
                change_rate = ((last_price - first_price) / first_price * 100) if first_price != 0 else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("起始单价", f"¥{first_price:.4f}")
                with col2:
                    st.metric("最新单价", f"¥{last_price:.4f}")
                with col3:
                    st.metric("变化率", f"{change_rate:+.2f}%")

def render_page_analysis(page_id: str, page_data: Dict[str, pd.DataFrame]):
    """根据页面类型渲染对应的分析结果"""
    
    if page_id == "cost_analysis":
        # 成本分析页面 - 使用综合数据或成本数据
        if 'comprehensive' in page_data and not page_data['comprehensive'].empty:
            render_analysis_results(page_data['comprehensive'])
        elif 'cost' in page_data and not page_data['cost'].empty:
            render_analysis_results(page_data['cost'])
        else:
            st.warning("暂无成本分析数据")
    
    elif page_id == "quantity_trend":
        # 数量趋势页面
        st.subheader("📈 数量趋势分析")
        if 'quantity_trend' in page_data and not page_data['quantity_trend'].empty:
            render_quantity_trend_analysis(page_data['quantity_trend'])
        if 'cost' in page_data and not page_data['cost'].empty:
            render_cost_quantity_analysis(page_data['cost'])
        if not any(page_data.values()):
            st.warning("暂无数量趋势数据")
    
    elif page_id == "price_analysis":
        # 单价分析页面
        st.subheader("💲 单价分析")
        if 'unit_price' in page_data and not page_data['unit_price'].empty:
            render_unit_price_analysis(page_data['unit_price'])
        if 'cost' in page_data and not page_data['cost'].empty:
            render_cost_price_analysis(page_data['cost'])
        if not any(page_data.values()):
            st.warning("暂无单价分析数据")
    
    elif page_id == "comprehensive":
        # 综合分析页面 - 显示所有数据类型
        st.subheader("🔍 综合分析")
        
        # 使用现有的render_analysis_results函数
        if 'comprehensive' in page_data and not page_data['comprehensive'].empty:
            render_analysis_results(page_data['comprehensive'])
        
        # 额外显示数量趋势
        if 'quantity_trend' in page_data and not page_data['quantity_trend'].empty:
            st.divider()
            st.subheader("数量趋势补充分析")
            render_quantity_trend_analysis(page_data['quantity_trend'])
        
        # 额外显示单价分析
        if 'unit_price' in page_data and not page_data['unit_price'].empty:
            st.divider()
            st.subheader("单价分析补充")
            render_unit_price_analysis(page_data['unit_price'])
        
        if not any(page_data.values()):
            st.warning("暂无综合分析数据")

def render_cost_quantity_analysis(df: pd.DataFrame):
    """基于成本数据渲染数量分析"""
    if df.empty or 'QUAN' not in df.columns:
        return
    
    st.subheader("基于成本数据的数量分析")
    
    # 按日期汇总数量
    if 'DATE' in df.columns:
        daily_quantity = df.groupby('DATE')['QUAN'].sum().reset_index()
        
        fig = px.line(daily_quantity, x='DATE', y='QUAN',
                     title='日度数量汇总趋势',
                     labels={'QUAN': '数量', 'DATE': '日期'})
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

def render_cost_price_analysis(df: pd.DataFrame):
    """基于成本数据渲染价格分析"""
    if df.empty or 'STD_COST' not in df.columns:
        return
    
    st.subheader("基于成本数据的价格分析")
    
    # 平均单价趋势
    if 'DATE' in df.columns and 'INV' in df.columns:
        # 选择前几个物料进行展示
        top_materials = df.groupby('INV')['TOTAL_COST'].sum().nlargest(5).index
        price_data = df[df['INV'].isin(top_materials)]
        
        if not price_data.empty:
            fig = px.line(price_data, x='DATE', y='STD_COST', color='INV',
                         title='主要物料单价趋势',
                         labels={'STD_COST': '单价 (¥)', 'DATE': '日期', 'INV': '物料'})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

def main():
    """主函数 - 集成统一数据加载器和分页管理器"""
    
    # 渲染页面选择器
    current_page = page_manager.render_page_selector()
    page_config = page_manager.get_page_config(current_page)
    
    st.title(f"{page_config.title}")
    
    # 初始化session state
    session_key = f'{current_page}_data'
    filters_key = f'{current_page}_filters'
    messages_key = f'{current_page}_messages'
    
    if session_key not in st.session_state:
        st.session_state[session_key] = {}
    if filters_key not in st.session_state:
        st.session_state[filters_key] = {}
    if messages_key not in st.session_state:
        st.session_state[messages_key] = []
    
    # 处理重置筛选
    if st.session_state.get('reset_filters', False):
        # 清除当前页面相关的session state
        keys_to_remove = [key for key in st.session_state.keys() 
                         if key.startswith(current_page)]
        for key in keys_to_remove:
            del st.session_state[key]
        st.session_state.reset_filters = False
        st.session_state[session_key] = {}
        st.session_state[filters_key] = {}
        st.session_state[messages_key] = []
    
    # 渲染侧边栏筛选器
    filters = render_sidebar_filters()
    
    # 处理数据加载和分析
    if filters['load_data']:
        with st.spinner(f"正在加载{page_config.title}数据..."):
            
            # 构建筛选条件字典
            filter_dict = {}
            if filters.get('selected_dept') and filters['selected_dept'] != "全部":
                filter_dict['dept_filter'] = filters['selected_dept']
            if filters.get('selected_inv') and filters['selected_inv'] != "全部":
                filter_dict['inv_filter'] = filters['selected_inv']
            
            # 使用页面管理器加载数据
            page_data = page_manager.load_page_data(
                current_page, 
                filters['start_date'], 
                filters['end_date'],
                filter_dict if filter_dict else None
            )
            
            if page_data:
                # 检查是否有有效数据
                has_data = any(not df.empty for df in page_data.values())
                
                if has_data:
                    st.toast(f"成功加载{page_config.title}数据")
                    
                    # 存储数据和筛选条件到session state
                    st.session_state[session_key] = page_data
                    st.session_state[filters_key] = filters
                    
                else:
                    st.warning("筛选条件下没有匹配的数据，请调整筛选条件")
            else:
                st.warning("指定时间范围内没有数据")
    
    # 如果session state中有数据，显示分析结果
    if st.session_state[session_key]:
        render_page_analysis(current_page, st.session_state[session_key])

if __name__ == "__main__":
    main()