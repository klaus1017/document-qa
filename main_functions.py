# =============================================================================
# 主要功能函数和界面渲染
# =============================================================================

def render_analysis_results_part2(df, monthly_material_summary, variance_analysis):
    """渲染分析结果的第二部分 - 物料分析、单价分析等"""
    
    # 继续tab4 - 单价分析
    tab4, tab5, tab6 = st.tabs(["物料分析", "月度趋势", "AI分析"])
    
    with tab4:
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
                        
                        # 单耗变差分析
                        st.subheader("物料单耗变差前10名明细")
                        
                        # 计算月度变化
                        material_trend_sorted = material_trend.sort_values(['INV', 'YEAR_MONTH'])
                        material_trend_sorted['上月单耗'] = material_trend_sorted.groupby('INV')['UNIT_CONSUMPTION'].shift(1)
                        material_trend_sorted['单耗变差'] = material_trend_sorted['UNIT_CONSUMPTION'] - material_trend_sorted['上月单耗']
                        material_trend_sorted['单耗变差百分比'] = (material_trend_sorted['单耗变差'] / material_trend_sorted['上月单耗'] * 100).round(2)
                        
                        # 筛选最近月份的数据
                        latest_month = material_trend_sorted['YEAR_MONTH'].max()
                        current_month_unit_changes = material_trend_sorted[
                            (material_trend_sorted['YEAR_MONTH'] == latest_month) & 
                            (material_trend_sorted['单耗变差百分比'].notna())
                        ].copy()
                        
                        current_month_unit_changes['单耗变差绝对值'] = current_month_unit_changes['单耗变差百分比'].abs()
                        top_unit_changes = current_month_unit_changes.nlargest(10, '单耗变差绝对值')
                        
                        if not top_unit_changes.empty:
                            display_unit_changes_df = top_unit_changes[['INV', 'YEAR_MONTH', 'UNIT_CONSUMPTION', '上月单耗', '单耗变差', '单耗变差百分比']].copy()
                            display_unit_changes_df.columns = ['物料', '当前月份', '当月单耗', '上月单耗', '单耗变差', '单耗变差百分比(%)']
                            
                            try:
                                st.dataframe(
                                    display_unit_changes_df.style.format({
                                        '当月单耗': '¥{:.2f}',
                                        '上月单耗': '¥{:.2f}',
                                        '单耗变差': '¥{:+.2f}',
                                        '单耗变差百分比(%)': '{:+.2f}%'
                                    }),
                                    use_container_width=True
                                )
                            except Exception:
                                st.dataframe(display_unit_changes_df, use_container_width=True)
                        else:
                            st.info("没有足够的月度数据进行单耗变差分析")
                    else:
                        st.info("该部门没有物料单耗趋势数据")
                else:
                    st.info("该部门没有物料数据")
        
        # 添加物料单耗趋势对比功能
        st.divider()
        st.subheader("物料单耗趋势对比")
        
        if not monthly_material_summary.empty:
            # 获取所有物料列表
            all_materials = monthly_material_summary['INV'].unique()
            
            # 多选物料控件
            selected_materials = st.multiselect(
                "选择要对比的物料（可选择多个）:",
                options=all_materials,
                default=[],
                help="选择你要对比单耗趋势的物料，最多建议选择8个以便于查看"
            )
            
            if selected_materials:
                # 筛选选中物料的数据
                material_comparison_data = monthly_material_summary[
                    monthly_material_summary['INV'].isin(selected_materials)
                ].copy()
                
                if not material_comparison_data.empty:
                    # 准备趋势图数据
                    material_trend_comparison = material_comparison_data.groupby(['INV', 'YEAR_MONTH']).agg({
                        'UNIT_CONSUMPTION': 'mean',
                        'TOTAL_COST': 'sum',
                        'QUAN': 'sum',
                        'DEPT_NAME_STD': 'first'
                    }).reset_index()
                    
                    # 转换年月为字符串便于显示
                    material_trend_comparison['年月字符串'] = material_trend_comparison['YEAR_MONTH'].astype(str)
                    
                    # 绘制单耗趋势对比图
                    fig_comparison = px.line(
                        material_trend_comparison,
                        x='年月字符串',
                        y='UNIT_CONSUMPTION',
                        color='INV',
                        title='选定物料单耗趋势对比',
                        labels={'UNIT_CONSUMPTION': '单耗 (¥)', '年月字符串': '年月', 'INV': '物料'},
                        markers=True
                    )
                    fig_comparison.update_layout(
                        height=600,
                        hovermode='x unified',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    st.plotly_chart(fig_comparison, use_container_width=True)
                    
                    # 显示对比数据表
                    st.subheader("物料单耗对比数据详情")
                    comparison_table = material_trend_comparison.pivot_table(
                        index='年月字符串',
                        columns='INV',
                        values='UNIT_CONSUMPTION',
                        aggfunc='mean'
                    ).fillna(0)
                    
                    # 重命名索引
                    comparison_table.index.name = '年月'
                    
                    # 添加平均值行
                    avg_row = comparison_table.mean()
                    avg_row.name = '平均值'
                    comparison_table = pd.concat([comparison_table, avg_row.to_frame().T])
                    
                    try:
                        st.dataframe(
                            comparison_table.style.format('¥{:.2f}'),
                            use_container_width=True
                        )
                    except Exception:
                        st.dataframe(comparison_table, use_container_width=True)
                    
                    # 添加统计摘要
                    st.subheader("统计摘要")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 最高/最低单耗物料
                        avg_consumption = material_trend_comparison.groupby('INV')['UNIT_CONSUMPTION'].mean().sort_values(ascending=False)
                        
                        st.write("**平均单耗排名:**")
                        for i, (material, consumption) in enumerate(avg_consumption.items(), 1):
                            st.write(f"{i}. {material}: ¥{consumption:.2f}")
                    
                    with col2:
                        # 趋势变化分析
                        st.write("**趋势变化分析:**")
                        for material in selected_materials:
                            material_data = material_trend_comparison[material_trend_comparison['INV'] == material].sort_values('YEAR_MONTH')
                            if len(material_data) >= 2:
                                first_value = material_data.iloc[0]['UNIT_CONSUMPTION']
                                last_value = material_data.iloc[-1]['UNIT_CONSUMPTION']
                                change_rate = ((last_value - first_value) / first_value * 100) if first_value != 0 else 0
                                trend_indicator = "📈" if change_rate > 0 else "📉" if change_rate < 0 else "➡️"
                                st.write(f"{trend_indicator} {material}: {change_rate:+.2f}%")
                else:
                    st.warning("选定物料没有数据可供对比")
            else:
                st.info("请选择要对比的物料")
        else:
            st.warning("没有物料数据可供分析")
    
    with tab5:
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
        
        # 月度单价变差分析（跟上个月对比）
        st.subheader("月度单价变差前10名明细")
        
        # 添加年月字段
        unit_price_df['年月'] = pd.to_datetime(unit_price_df['DATE']).dt.to_period('M')
        
        # 按物料和月份计算平均单价
        monthly_price = unit_price_df.groupby(['INV', '年月'])['UNIT_PRICE'].mean().reset_index()
        
        # 计算月度单价变化
        monthly_price = monthly_price.sort_values(['INV', '年月'])
        monthly_price['上月单价'] = monthly_price.groupby('INV')['UNIT_PRICE'].shift(1)
        monthly_price['单价变差'] = monthly_price['UNIT_PRICE'] - monthly_price['上月单价']
        monthly_price['单价变差百分比'] = (monthly_price['单价变差'] / monthly_price['上月单价'] * 100).round(2)
        
        # 筛选最近月份的数据
        latest_month = monthly_price['年月'].max()
        current_month_price_changes = monthly_price[
            (monthly_price['年月'] == latest_month) & 
            (monthly_price['单价变差百分比'].notna())
        ].copy()
        
        current_month_price_changes['单价变差绝对值'] = current_month_price_changes['单价变差百分比'].abs()
        top_price_changes = current_month_price_changes.nlargest(10, '单价变差绝对值')
        
        if not top_price_changes.empty:
            display_price_changes_df = top_price_changes[['INV', '年月', '单价变差百分比']].copy()
            display_price_changes_df.columns = ['物料', '当前月份', '变差百分比(%)']
            
            try:
                st.dataframe(
                    display_price_changes_df.style.format({
                        '变差百分比(%)': '{:+.2f}%'
                    }),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(display_price_changes_df, use_container_width=True)
        else:
            st.info("没有足够的月度数据进行单价变差分析")
        
        # 原有的单价波动预警功能
        st.subheader("单价波动预警详情")
        
        # 计算每日单价变化率
        unit_price_df = unit_price_df.sort_values(by=['INV', 'DATE'])
        unit_price_df['PREV_UNIT_PRICE'] = unit_price_df.groupby('INV')['UNIT_PRICE'].shift(1)
        unit_price_df['PRICE_CHANGE_PCT'] = (unit_price_df['UNIT_PRICE'] - unit_price_df['PREV_UNIT_PRICE']) / unit_price_df['PREV_UNIT_PRICE']
        unit_price_df['PRICE_CHANGE_PCT'] = unit_price_df['PRICE_CHANGE_PCT'].replace([np.inf, -np.inf], np.nan).fillna(0)

        # 设置预警阈值 (例如：单价变化超过5%)
        warning_threshold = 0.05
        unit_price_df['IS_WARNING'] = (unit_price_df['PRICE_CHANGE_PCT'].abs() > warning_threshold)

        # 筛选出有预警的料号
        all_invs = unit_price_df['INV'].unique()

        if len(all_invs) > 0:
            st.write("选择料号查看单价趋势：")
            selected_inv = st.selectbox("", all_invs, key='price_inv_select')

            # 检查是否有预警，并显示预警信息
            warning_invs = unit_price_df[unit_price_df['IS_WARNING']]['INV'].unique()
            if selected_inv in warning_invs:
                st.warning(f"料号 {selected_inv} 存在单价波动预警 (变化超过 {warning_threshold:.1%})。")
            else:
                st.info(f"料号 {selected_inv} 当前没有单价波动预警。")

            inv_data = unit_price_df[unit_price_df['INV'] == selected_inv].copy()
            inv_data = inv_data.sort_values('DATE')

            # 绘制单价趋势图
            fig_price = px.line(inv_data, x='DATE', y='UNIT_PRICE', title=f"{selected_inv} 单价趋势")
            
            # 标记预警点
            warning_points = inv_data[inv_data['IS_WARNING']]
            if not warning_points.empty:
                fig_price.add_trace(go.Scatter(
                    mode='markers',
                    x=warning_points['DATE'],
                    y=warning_points['UNIT_PRICE'],
                    marker=dict(color='red', size=10, symbol='star'),
                    name='预警点',
                    hovertext=warning_points.apply(lambda row: f"日期: {row['DATE'].strftime('%Y-%m-%d')}<br>单价: {row['UNIT_PRICE']:.4f}<br>变化: {row['PRICE_CHANGE_PCT']:.2%}", axis=1)
                ))

            fig_price.update_xaxes(title_text="日期")
            fig_price.update_yaxes(title_text="单价")
            st.plotly_chart(fig_price, use_container_width=True)

            # 显示详细预警数据
            st.subheader(f"{selected_inv} 单价波动预警数据")
            display_price_warning_df = inv_data[inv_data['IS_WARNING']][['DATE', 'INV', 'PRICE_CHANGE_PCT']].copy()
            display_price_warning_df.columns = ['日期', '料号', '单价变化率']
            try:
                st.dataframe(
                    display_price_warning_df.style.format({
                        '单价变化率': '{:+.2%}'
                    }),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(display_price_warning_df, use_container_width=True)
        else:
            st.info("当前日期范围内没有料号的单价波动超过预警阈值。")
    else:
        st.warning("无法加载单价数据。")
            
    with tab6:
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
                        
                        # 为每条助手回答添加导出按钮
                        if message["content"] and not message["content"].startswith("调用本地 LLM"):
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"单耗分析报告_{timestamp}.docx"
                            
                            # 准备分析上下文信息
                            date_range = "未知"
                            if 'DATE' in df.columns:
                                min_date = df['DATE'].min().strftime('%Y-%m-%d') if not df['DATE'].isna().all() else '未知'
                                max_date = df['DATE'].max().strftime('%Y-%m-%d') if not df['DATE'].isna().all() else '未知'
                                date_range = f"{min_date} 至 {max_date}"
                            elif 'YYYYMM' in df.columns:
                                min_ym = df['YYYYMM'].min() if not df['YYYYMM'].isna().all() else '未知'
                                max_ym = df['YYYYMM'].max() if not df['YYYYMM'].isna().all() else '未知'
                                date_range = f"{min_ym} 至 {max_ym}"
                                
                            analysis_context = {
                                'date_range': date_range,
                                'total_records': len(df),
                                'llm_model': llm_model_name,
                                'data_summary': {
                                    '分析记录数': len(df),
                                    '数据列数': len(df.columns),
                                    '总成本': f"¥{df['TOTAL_COST'].sum():,.2f}",
                                    '总数量': f"{df['QUAN'].sum():,.0f}",
                                    '部门数量': df['DEPT_NAME_STD'].nunique(),
                                    '物料种类': df['INV'].nunique()
                                }
                            }
                            
                            try:
                                # 生成Word报告
                                with st.spinner(f"正在生成第{i+1}条回答的报告..."):
                                    user_question = ""
                                    if i > 0 and st.session_state.cost_llm_messages[i-1]["role"] == "user":
                                        user_question = st.session_state.cost_llm_messages[i-1]["content"]
                                    elif i == 0:
                                        user_question = "初始分析"
                                    
                                    doc_io = generate_word_report(user_question, message["content"], analysis_context)
                                
                                # 添加下载按钮
                                st.download_button(
                                    label=f"导出第{i+1}条回答为Word报告",
                                    data=doc_io.getvalue(),
                                    file_name=filename,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"export_word_msg_{i}_{len(st.session_state.cost_llm_messages)}",
                                    help="点击下载Word格式的分析报告",
                                    use_container_width=True
                                )
                                
                            except Exception as export_err:
                                st.error(f"生成报告失败: {export_err}")
        
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

def apply_filters_to_data(df, filters):
    """应用筛选条件到数据"""
    if df.empty:
        return df
    
    filtered_df = df.copy()
    
    # 部门筛选 - 使用DEPT_NAME_STD字段
    if filters['selected_dept'] != "全部":
        filtered_df = filtered_df[filtered_df['DEPT_NAME_STD'] == filters['selected_dept']]
    
    # 物料筛选
    if filters['selected_inv'] != "全部":
        filtered_df = filtered_df[filtered_df['INV'] == filters['selected_inv']]
    
    return filtered_df