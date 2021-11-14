let startDate;
let endDate;
let granularity;
let baseCurrency;
let options;

$(document).ready(function () {
    // setup start date picker
    let startDatePicker = $('#startDatePicker');
    startDatePicker.datepicker({
        format: 'yyyy-mm-dd',
        container: $('#startPickerContainer'),
        todayHighlight: true,
        autoclose: true,
    });
    startDatePicker.on('change', () => {
        startDate = $('#startDatePicker').val()
    })

    // setup end date picker
    let endDatePicker = $('#endDatePicker');
    endDatePicker.datepicker({
        format: 'yyyy-mm-dd',
        container: $('#endPickerContainer'),
        todayHighlight: true,
        autoclose: true,
    });
    endDatePicker.on('change', () => {
        endDate = $('#endDatePicker').val()
    })

    $('#granularitySelectPicker').on('change', () => {
        granularity = $('#granularitySelectPicker').val()
    })


    $('#currencySelectPicker').on('change', () => {
        options = $('#currencySelectPicker').val()
        if (options) {
            let currencyOptions = options.map(option => {
                return `<option>${option}</option>`
            }).join()
            let newSelect = `<select id="currencyBaseSelector" title="Base Currency (x-axis)" class="selectpicker ma1" data-live-search="true">${currencyOptions}</select>`
            let basePicker = $('#currencyBasePicker')
            basePicker.empty()
            basePicker.append(newSelect)
            let baseSelector = $('#currencyBaseSelector')
            baseSelector.selectpicker({})
            baseSelector.on('change', () => {
                baseCurrency = $('#currencyBaseSelector').val()
            })
        }
    })

    $('#collectRun').on('click', () => {
        $('#collectRun').prop('disabled', true)
        $.get({
            url: '/currency/target',
            headers: {
                startDate,
                endDate,
                granularity,
                baseCurrency,
                currencies: options.join(','),
            },
        }, resp => {
            console.log(resp.data)
            $('#collectRun').prop('disabled', false)
        })
    })

    // setup line chart
    let ctx = $('#line-chart')
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: [1500, 1600, 1700, 1750, 1800, 1850, 1900, 1950, 1999, 2050],
            datasets: [{
                data: [86, 114, 106, 106, 107, 111, 133, 221, 783, 2478],
                label: "Africa",
                borderColor: "#3e95cd",
                fill: false
            }, {
                data: [282, 350, 411, 502, 635, 809, 947, 1402, 3700, 5267],
                label: "Asia",
                borderColor: "#8e5ea2",
                fill: false
            }, {
                data: [168, 170, 178, 190, 203, 276, 408, 547, 675, 734],
                label: "Europe",
                borderColor: "#3cba9f",
                fill: false
            }, {
                data: [40, 20, 10, 16, 24, 38, 74, 167, 508, 784],
                label: "Latin America",
                borderColor: "#e8c3b9",
                fill: false
            }, {
                data: [6, 3, 2, 2, 7, 26, 82, 172, 312, 433],
                label: "North America",
                borderColor: "#c45850",
                fill: false
            }
            ]
        },
        options: {
            title: {
                display: true,
                text: 'World population per region (in millions)'
            }
        }
    });
})

function refreshData() {
    document.querySelector("button#refreshButton").setAttribute('disabled', true)
    $('#refreshButton').prop('disabled', true)
    $.get('/currency/refresh', resp => {
        console.log(resp.currencies)
        $('#refreshButton').prop('disabled', false)
    })
}
function getRates() {

}
function gatherData() {
    document.querySelector("button#gatherButton").setAttribute('disabled', true)
    startDate = new Date('2021-10-31')
    startDateString = startDate.toISOString()
    endDate = new Date('2021-11-11')
    endDateString = endDate.toISOString()
    currencies = ['xua', 'usd', 'gbp']
    $.get({
        url: '/currency/target',
        headers: {
            currencies,
            startDate: startDateString,
            endDate: endDateString,
        },
    }, resp => {
        document.querySelector("button#gatherButton").setAttribute('disabled', false)
        console.log(resp.data)
    })
}