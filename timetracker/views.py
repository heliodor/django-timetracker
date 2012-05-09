'''
Views which are mapped from the URL objects in urls.py
'''

import datetime

from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from tracker.models import Tbluser, UserForm, TrackingEntry
from tracker.models import Tblauthorization as tblauth
from tracker.forms import EntryForm, AddForm, Login

from utils.datemaps import generate_select
from utils.calendar_utils import (gen_calendar, ajax_add_entry,
                                  ajax_change_entry, ajax_delete_entry,
                                  ajax_error, get_user_data, admin_check,
                                  delete_user, useredit, mass_holidays,
                                  profile_edit)

def loggedin(func):

    """
    Decorator to make sure that the view is being accessed
    by a logged in user
    """

    def inner(request, *args, **kwargs):
        try:
            get_object_or_404(Tbluser, id=request.session.get("user_id"))
        except Tbluser.DoesNotExist:
            raise Http404
        except TypeError:
            raise Http404

        return func(request)

    return inner

def index(request):

    """
    Serve the root page, there's nothing there at the moment
    """
    return render_to_response('index.html',
                              {'login': Login()},
                              RequestContext(request))


def login(request):

    """
    Basic login function.

    Dispatches to admin/user depending on usertype
    """

    # if this somehow gets requested via Ajax, then
    # send back a 404.
    if request.is_ajax():
        raise Http404

    # if the csrf token is missing, that's a 404
    if not request.POST.get('csrfmiddlewaretoken', None):
        raise Http404

    try:
        # pull out the user from the POST and
        # match it against our db
        usr = Tbluser.objects.get(user_id__exact=request.POST['user_name'])

    # if the user doesn't match anything, notify
    except Tbluser.DoesNotExist:
        return HttpResponse("Username and Password don't match")

    if usr.password == request.POST['password']:

        # if all goes well, send to the tracker
        request.session['user_id'] = usr.id
        request.session['firstname'] = usr.firstname

        if usr.user_type == "ADMIN":
            return HttpResponseRedirect("/admin_view/")
        else:
            return HttpResponseRedirect("/calendar/")
    else:
        return HttpResponse("Login failed!")


def logout(request):

    """
    Simple logout function
    """

    try:
        del request.session['user_id']
    except KeyError:
        pass

    return HttpResponseRedirect("/")

@loggedin
def user_view(request,
             year=datetime.date.today().year,
             month=datetime.date.today().month,
             day=datetime.date.today().day,
             ):

    """
    Generates a calendar based on the URL it receives.
    site.com/calendar/2012/02/, also takes a day
    just in case you want to add a particular view for a day,
    for example.

    The generated HTML is pretty printed
    """

    user_id = request.session['user_id']
    calendar_table = gen_calendar(year, month, day,
                                  user=user_id)
    balance = Tbluser.objects.get(id=user_id).get_total_balance(ret='int')
    return render_to_response(
        'calendar.html',
        {
         'calendar': calendar_table,
         'changeform': EntryForm(),
         'addform': AddForm(),
         'welcome_name': request.session['firstname'],
         'balance': balance
        },
        RequestContext(request)
        )


def ajax(request):

    """
    Ajax request handler, dispatches to specific ajax functions
    depending on what json gets sent.
    """

    # if the page is accessed via the browser (or other means)
    # we don't serve requests
    if not request.is_ajax():
        raise Http404

    # see which form we're dealing with
    form_type = request.POST.get('form_type', None)

    #if there isn't one, we'll send an error back
    if not form_type:
        return ajax_error("Missing Form")

    # this could be mutated with a @register_ajax
    # decorator or something
    ajax_funcs = {
        'add': ajax_add_entry,
        'change': ajax_change_entry,
        'delete': ajax_delete_entry,
        'admin_get': gen_calendar,
        'get_user_data': get_user_data,
        'useredit': useredit,
        'delete_user': delete_user,
        'mass_holidays': mass_holidays,
        'profileedit': profile_edit
        }
    return ajax_funcs.get(form_type,
                          ajax_error("Form not found")
                          )(request)


@admin_check
def admin_view(request):

    """
    The user logged in is an admin, we show them a
    view based on their team
    """

    admin_id = request.session.get("user_id", None)

    try:
        employees = tblauth.objects.get(admin=admin_id)
    except tblauth.DoesNotExist:
        employees = []

    return render_to_response("admin_view.html",
                              {"employees": employees,
                               'welcome_name': request.session['firstname']},
                               RequestContext(request))


@admin_check
def add_change_user(request):

    """
    Creates the view for changing/adding users
    """

    admin_id = request.session.get('user_id', None)

    try:
        employees = tblauth.objects.get(admin_id=admin_id)
    except tblauth.DoesNotExist:
        employees = []

    # generate the select dropdown for all employees
    all_employees = generate_select([(user.id, user.name()) for user in Tbluser.objects.filter(user_type='RUSER')],
                                    id="all_employee_select")

    return render_to_response(
        "useredit.html",
        {
        "employees": employees,
        "user_form": UserForm(),
        'welcome_name': request.session['firstname'],
        'all_employees': all_employees
        },
        RequestContext(request)
    )


@admin_check
def holiday_planning(request,
                     year=datetime.datetime.today().year,
                     month=datetime.datetime.today().month):
    """
    Generates the full holiday table for all employees under a manager
    """

    try:
        auth = tblauth.objects.get(admin_id=request.session.get('user_id'))
    except tblauth.DoesNotExist:
        return HttpResponseRedirect("/admin_view/")

    return render_to_response(
        "holidays.html",
        {
        "holiday_table": auth.gen_holiday_list(int(year),
                                               int(month)),
        'welcome_name': request.session['firstname']
        },
        RequestContext(request))

@loggedin
def edit_profile(request):

    """
    View for sending the user to the edit profile page
    """

    user = Tbluser.objects.get(id=request.session.get("user_id"))

    balance = user.get_total_balance(ret='int')
    return render_to_response("editprofile.html",
                              {'firstname': user.firstname,
                               'lastname': user.lastname,
                               'welcome_name': request.session['firstname'],
                               'balance': balance
                               },
                              RequestContext(request))

@loggedin
def explain(request):

    """
    Renders the Balance explanation page
    """

    user = Tbluser.objects.get(id=request.session.get("user_id"))
    shift = str(user.shiftlength.hour) + ':' + str(user.shiftlength.minute)
    working_days = TrackingEntry.objects.filter(user=user.id).count()

    balance = user.get_total_balance(ret='int')
    return render_to_response("balance.html",
                              {'firstname': user.firstname,
                               'lastname': user.lastname,
                               'welcome_name': request.session['firstname'],
                               'balance': balance,
                               'shiftlength': shift,
                               'working_days': working_days
                               },
                              RequestContext(request))
